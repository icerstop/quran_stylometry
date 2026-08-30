"""T-008 â€” `save_fig` zapisuje komplet plikow i egzekwuje G9.

Sedno: figura wynikowa bez kotwicy kontrolnej nie ma prawa powstac. Regula jest
tu w kodzie, a nie w dokumentacji, wiec sprawdzamy ja jak kazdy inny kontrakt.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from src.config import Config  # noqa: E402
from src.schemas import GuardrailViolationError  # noqa: E402
from src.viz.fig00_smoke import run as run_smoke  # noqa: E402
from src.viz.save import FigureSpec, save_fig, upsert_index_entry  # noqa: E402
from src.viz.style import CATEGORICAL_PALETTE, apply_style  # noqa: E402


def make_spec(**overrides: object) -> FigureSpec:
    payload: dict[str, object] = {
        "fig_id": "FIG-15",
        "slug": "variance_scale",
        "experiment": "E-05",
        "shows": "Rozklady V_single i V_mixture-2 z pozycja Koranu.",
        "reads_as": "Czytaj pozycje pionowej linii wzgledem obu rozkladow.",
        "do_not_conclude": "Nie wnioskuj o liczbie autorow.",
        "control_anchor": "V_mixture-2 oraz V_within-surah w tym samym panelu",
    }
    payload.update(overrides)
    return FigureSpec(**payload)  # type: ignore[arg-type]


@pytest.fixture
def figure() -> Figure:
    apply_style()
    fig, ax = plt.subplots()
    ax.plot([0, 1, 2], [1, 3, 2])
    return fig


def test_saves_png_svg_and_json(figure: Figure, tmp_path: Path) -> None:
    saved = save_fig(
        figure,
        make_spec(),
        {"values": [1, 3, 2]},
        config_hash="abc123",
        out_dir=tmp_path,
        index_path=tmp_path / "INDEX.md",
    )
    assert saved.png.exists() and saved.png.stat().st_size > 0
    assert saved.svg.exists() and saved.svg.stat().st_size > 0
    assert saved.json.exists()

    payload = json.loads(saved.json.read_text(encoding="utf-8"))
    assert payload["fig_id"] == "FIG-15"
    assert payload["config_hash"] == "abc123"
    assert payload["data"] == {"values": [1, 3, 2]}
    assert "git_sha" in payload


def test_result_figure_without_control_anchor_is_rejected() -> None:
    """G9 â€” figura bez kotwicy nie wchodzi do raportu, wiec nie powstaje."""
    with pytest.raises(GuardrailViolationError, match="G9"):
        make_spec(control_anchor=None)
    with pytest.raises(GuardrailViolationError, match="G9"):
        make_spec(control_anchor="   ")


def test_diagnostic_figure_may_skip_control_anchor() -> None:
    spec = make_spec(fig_id="FIG-07", slug="domain_probe", kind="diagnostic", control_anchor=None)
    assert spec.kind == "diagnostic"


def test_empty_data_is_rejected(figure: Figure, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="nieweryfikowalna"):
        save_fig(figure, make_spec(), {}, out_dir=tmp_path, index_path=tmp_path / "INDEX.md")


def test_index_entry_answers_all_four_questions(figure: Figure, tmp_path: Path) -> None:
    index_path = tmp_path / "INDEX.md"
    save_fig(figure, make_spec(), {"v": 1}, out_dir=tmp_path, index_path=index_path)

    content = index_path.read_text(encoding="utf-8")
    assert "FIG-15" in content
    assert "Pokazuje:" in content
    assert "Jak czytac:" in content
    assert "Czego NIE wolno wnioskowac:" in content
    assert "Kotwica kontrolna (G9):" in content


def test_index_entry_is_upserted_not_duplicated(tmp_path: Path) -> None:
    index_path = tmp_path / "INDEX.md"
    upsert_index_entry(make_spec(), index_path=index_path)
    upsert_index_entry(make_spec(shows="Opis po aktualizacji."), index_path=index_path)

    content = index_path.read_text(encoding="utf-8")
    assert content.count("<!-- fig:FIG-15 -->") == 1
    assert "Opis po aktualizacji." in content


def test_index_keeps_other_entries(tmp_path: Path) -> None:
    index_path = tmp_path / "INDEX.md"
    upsert_index_entry(make_spec(), index_path=index_path)
    upsert_index_entry(make_spec(fig_id="FIG-16", slug="forest_percentiles"), index_path=index_path)
    upsert_index_entry(make_spec(shows="Zaktualizowany opis."), index_path=index_path)

    content = index_path.read_text(encoding="utf-8")
    assert "<!-- fig:FIG-15 -->" in content
    assert "<!-- fig:FIG-16 -->" in content


@pytest.mark.parametrize("bad_id", ["FIG15", "fig-15", "FIGURE-15", "FIG-1"])
def test_malformed_fig_id_is_rejected(bad_id: str) -> None:
    with pytest.raises(ValueError, match="fig_id"):
        make_spec(fig_id=bad_id)


def test_suffixed_fig_id_is_allowed() -> None:
    """Katalog figur zawiera FIG-06b i FIG-19b."""
    assert make_spec(fig_id="FIG-06b", slug="chronology_agreement").fig_id == "FIG-06b"


@pytest.mark.parametrize("field", ["shows", "reads_as", "do_not_conclude"])
def test_empty_description_fields_are_rejected(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        make_spec(**{field: "  "})


def test_palette_is_colourblind_safe() -> None:
    """Okabe-Ito: pierwsze dwie pozycje musza byc rozroznialne bez kontrastu R/G."""
    assert CATEGORICAL_PALETTE[0] == "#E69F00"
    assert CATEGORICAL_PALETTE[1] == "#56B4E9"
    assert len(set(CATEGORICAL_PALETTE)) == len(CATEGORICAL_PALETTE)


def test_smoke_figure_produces_full_set(tmp_path: Path) -> None:
    """To jest dokladnie to, co robi `make figs-smoke`."""
    saved = run_smoke(Config(), out_dir=tmp_path, index_path=tmp_path / "INDEX.md")
    for path in (saved.png, saved.svg, saved.json):
        assert path.exists()
    assert "FIG-00" in (tmp_path / "INDEX.md").read_text(encoding="utf-8")


def test_smoke_figure_is_deterministic(tmp_path: Path) -> None:
    first = run_smoke(Config(), out_dir=tmp_path / "a", index_path=tmp_path / "a" / "INDEX.md")
    second = run_smoke(Config(), out_dir=tmp_path / "b", index_path=tmp_path / "b" / "INDEX.md")

    data_a = json.loads(first.json.read_text(encoding="utf-8"))["data"]
    data_b = json.loads(second.json.read_text(encoding="utf-8"))["data"]
    assert data_a == data_b
