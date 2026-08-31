"""FIG-06 — internal_duplication_rate Koran vs gatunki CTRL (T-017).

Kotwica G9: ten sam 7-gramowy wskaźnik na tokenach potasowanych w obrębie
jednostki (sura / dzieło). Jeśli slupki shuffle ≈ raw, redundancja to Zipf,
nie formuła.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from src.paths import FIGURES_DIR, FIGURES_INDEX_PATH
from src.viz.save import FigureSpec, SavedFigure, save_fig
from src.viz.style import apply_style, role_color

SPEC = FigureSpec(
    fig_id="FIG-06",
    slug="internal_duplication",
    experiment="T-017",
    kind="result",
    families=["duplication"],
    control_anchor=(
        "shuffle: permutacja tokenów w obrębie sury (Koran) / dzieła (CTRL), "
        "ten sam n=7; wąsy = SD po jednostkach"
    ),
    shows=(
        "Odsetek typów 7-gramów występujących ≥ 2 razy: Koran, CTRL łącznie "
        "i per gatunek, obok shuffle."
    ),
    reads_as=(
        "Wysoki raw przy niskim shuffle = powtórzenia sekwencji (formuła, "
        "refren), nie sam rozkład częstości słów. Wariant dedup jest w JSON."
    ),
    do_not_conclude=(
        "Nie wnioskuj o autorstwie Koranu. To diagnostyka korpusu (F-11), "
        "nie V. T-041 (kotwice RQ6) jeszcze nie istnieje — nie ma ich na figurze."
    ),
)


def _rate(block: dict[str, Any], *, shuffled: bool) -> float:
    key = "shuffle" if shuffled else "raw"
    payload = block.get(key) or {}
    return float(payload.get("internal_duplication_rate") or 0.0)


def _std(block: dict[str, Any], *, shuffled: bool) -> float:
    key = "shuffle_unit_rate_std" if shuffled else "unit_rate_std"
    return float(block.get(key) or 0.0)


def make_fig_06(payload: dict[str, Any]) -> tuple[Figure, dict[str, object]]:
    apply_style()
    by_genre: dict[str, Any] = dict(payload.get("by_genre") or {})
    genre_order = sorted(
        by_genre,
        key=lambda g: -int((by_genre[g].get("n_tokens") or 0)),
    )
    labels = ["quran", "ctrl"] + genre_order
    blocks = [payload.get("quran") or {}, payload.get("ctrl") or {}] + [
        by_genre[g] for g in genre_order
    ]
    raw = [_rate(b, shuffled=False) for b in blocks]
    shuf = [_rate(b, shuffled=True) for b in blocks]
    err_raw = [_std(b, shuffled=False) for b in blocks]
    err_shuf = [_std(b, shuffled=True) for b in blocks]

    fig, ax = plt.subplots(figsize=(8.0, max(3.8, 0.38 * len(labels) + 1.6)))
    y = list(range(len(labels)))
    h = 0.36
    ax.barh(
        [v + h / 2 for v in y],
        raw,
        height=h,
        xerr=err_raw,
        color=role_color("quran"),
        label="raw",
        capsize=2,
    )
    ax.barh(
        [v - h / 2 for v in y],
        shuf,
        height=h,
        xerr=err_shuf,
        color=role_color("shuffle"),
        label="shuffle",
        capsize=2,
    )
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("internal_duplication_rate (typy 7-gramów, count ≥ 2)")
    ax.set_title("FIG-06 — T-017 redundancja wewnętrzna")
    ax.set_xlim(0, max(1.0, max(raw + shuf + [0.01]) * 1.15))
    ax.legend(loc="lower right")
    ax.invert_yaxis()

    data: dict[str, object] = {
        "labels": labels,
        "raw": raw,
        "shuffle": shuf,
        "unit_rate_std": err_raw,
        "shuffle_unit_rate_std": err_shuf,
        "control": "token_shuffle_within_unit",
    }
    return fig, data


def save_fig_06(
    payload: dict[str, Any],
    *,
    config_hash: str | None = None,
    out_dir: Path = FIGURES_DIR,
    index_path: Path = FIGURES_INDEX_PATH,
) -> SavedFigure:
    fig, data = make_fig_06(payload)
    return save_fig(
        fig, SPEC, data, config_hash=config_hash, out_dir=out_dir, index_path=index_path
    )
