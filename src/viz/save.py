"""Zapis figur i rejestr `figures/INDEX.md` (T-008).

Kazda figura zapisywana jest jako komplet: PNG + SVG + JSON z danymi zrodlowymi
+ wpis w INDEX.md. Brak ktoregokolwiek elementu oznacza, ze figury nie da sie
odtworzyc ani zweryfikowac, wiec zapis jest atomowy koncepcyjnie: albo caly
komplet, albo wyjatek.

G9 jest egzekwowany tutaj, w kodzie, a nie w dyscyplinie autora: figura o typie
`result` bez zadeklarowanej kotwicy kontrolnej (shuffle / mixture / pseudo-book /
baseline) nie zostanie zapisana.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from matplotlib.figure import Figure

from src.paths import FIGURES_DIR, FIGURES_INDEX_PATH
from src.schemas import GuardrailViolationError
from src.utils.io import ensure_dir, write_json
from src.utils.provenance import git_state, utc_now_iso

FigureKind = Literal["result", "diagnostic"]

FIG_ID_PATTERN = re.compile(r"^FIG-\d{2}[a-z]?$")
_ENTRY_PATTERN = re.compile(
    r"<!-- fig:(?P<fig_id>[A-Za-z0-9\-]+) -->.*?<!-- /fig:(?P=fig_id) -->\n?",
    re.DOTALL,
)

_INDEX_HEADER = """# INDEX figur

Rejestr generowany automatycznie przez `src.viz.save.save_fig`. Nie edytuj recznie
— kazdy wpis powstaje razem z plikami PNG/SVG/JSON i znika, gdy figura zniknie.

Kazdy wpis odpowiada na cztery pytania z `docs/06_FIGURES.md`: co pokazuje, jak
czytac, czego **nie** wolno wnioskowac, i jaka kotwice kontrolna niesie (G9).
"""


@dataclass(frozen=True)
class FigureSpec:
    """Opis figury. Pola tekstowe trafiaja 1:1 do INDEX.md."""

    fig_id: str
    slug: str
    experiment: str
    shows: str
    reads_as: str
    do_not_conclude: str
    control_anchor: str | None = None
    kind: FigureKind = "result"
    families: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not FIG_ID_PATTERN.match(self.fig_id):
            raise ValueError(
                f"fig_id musi miec postac 'FIG-07' albo 'FIG-06b', dostano {self.fig_id!r}"
            )
        if not self.slug or not re.fullmatch(r"[a-z0-9_]+", self.slug):
            raise ValueError(f"slug musi byc snake_case ASCII, dostano {self.slug!r}")
        for name in ("shows", "reads_as", "do_not_conclude"):
            if not getattr(self, name).strip():
                raise ValueError(
                    f"FigureSpec.{name} nie moze byc puste — INDEX.md ma byc uzyteczny"
                )
        if self.kind == "result" and not (self.control_anchor or "").strip():
            raise GuardrailViolationError(
                f"G9: figura {self.fig_id} ma typ 'result', ale nie deklaruje kotwicy "
                "kontrolnej. Figura bez kotwicy (shuffle / mixture / pseudo-book / "
                "baseline) nie wchodzi do raportu."
            )

    @property
    def stem(self) -> str:
        return f"{self.fig_id}_{self.slug}"


@dataclass(frozen=True)
class SavedFigure:
    png: Path
    svg: Path
    json: Path
    index: Path


def save_fig(
    fig: Figure,
    spec: FigureSpec,
    data: dict[str, Any],
    *,
    config_hash: str | None = None,
    out_dir: Path = FIGURES_DIR,
    index_path: Path = FIGURES_INDEX_PATH,
    close: bool = True,
) -> SavedFigure:
    """Zapisuje komplet plikow figury i aktualizuje INDEX.md."""
    if not data:
        raise ValueError(
            f"{spec.fig_id}: JSON z danymi zrodlowymi nie moze byc pusty — "
            "bez niego figura jest nieweryfikowalna."
        )

    ensure_dir(out_dir)
    png_path = out_dir / f"{spec.stem}.png"
    svg_path = out_dir / f"{spec.stem}.svg"
    json_path = out_dir / f"{spec.stem}.json"

    fig.savefig(png_path, format="png")
    fig.savefig(svg_path, format="svg")
    if close:
        import matplotlib.pyplot as plt

        plt.close(fig)

    state = git_state()
    write_json(
        json_path,
        {
            "fig_id": spec.fig_id,
            "slug": spec.slug,
            "experiment": spec.experiment,
            "kind": spec.kind,
            "control_anchor": spec.control_anchor,
            "families": spec.families,
            "shows": spec.shows,
            "reads_as": spec.reads_as,
            "do_not_conclude": spec.do_not_conclude,
            "config_hash": config_hash,
            "generated_at": utc_now_iso(),
            **state.to_dict(),
            "data": data,
        },
    )

    upsert_index_entry(spec, index_path=index_path)
    return SavedFigure(png=png_path, svg=svg_path, json=json_path, index=index_path)


def render_index_entry(spec: FigureSpec) -> str:
    anchor = spec.control_anchor or "brak (figura diagnostyczna)"
    families = ", ".join(spec.families) if spec.families else "-"
    return (
        f"<!-- fig:{spec.fig_id} -->\n"
        f"## {spec.fig_id} — {spec.slug}\n\n"
        f"- Eksperyment: {spec.experiment}\n"
        f"- Typ: {spec.kind}\n"
        f"- Rodziny cech: {families}\n"
        f"- Kotwica kontrolna (G9): {anchor}\n"
        f"- Pokazuje: {spec.shows}\n"
        f"- Jak czytac: {spec.reads_as}\n"
        f"- Czego NIE wolno wnioskowac: {spec.do_not_conclude}\n"
        f"- Pliki: `{spec.stem}.png`, `{spec.stem}.svg`, `{spec.stem}.json`\n"
        f"<!-- /fig:{spec.fig_id} -->\n"
    )


def upsert_index_entry(spec: FigureSpec, *, index_path: Path = FIGURES_INDEX_PATH) -> Path:
    """Wstawia albo podmienia wpis o danym `fig_id`, zachowujac reszte pliku."""
    ensure_dir(index_path.parent)
    existing = index_path.read_text(encoding="utf-8") if index_path.exists() else _INDEX_HEADER
    entry = render_index_entry(spec)

    marker = f"<!-- fig:{spec.fig_id} -->"
    if marker in existing:
        updated = _ENTRY_PATTERN.sub(
            lambda m: entry if m.group("fig_id") == spec.fig_id else m.group(0),
            existing,
        )
    else:
        updated = existing.rstrip("\n") + "\n\n" + entry

    index_path.write_text(updated, encoding="utf-8", newline="\n")
    return index_path
