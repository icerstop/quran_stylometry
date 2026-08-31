"""FIG-41 — top-K function words F2 (T-022).

Kotwica: srednie czestosci na CTRL-TEST (autorzy niewidziani przy fitowaniu).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from src.paths import FIGURES_DIR, FIGURES_INDEX_PATH
from src.viz.save import FigureSpec, SavedFigure, save_fig
from src.viz.style import apply_style, role_color

SPEC = FigureSpec(
    fig_id="FIG-41",
    slug="function_topk",
    experiment="T-022",
    kind="result",
    families=["function_words"],
    control_anchor=(
        "CTRL-TEST: te same K function words, autorzy niewidziani przy fitowaniu "
        "(G4). Quran i TRAIN w tym samym panelu."
    ),
    shows=(
        "Top-20 form funkcyjnych (POS whitelist, segmenty morfologiczne) wg "
        "sredniej czestosci wzglednej na CTRL-TRAIN, obok CTRL-TEST i Koranu."
    ),
    reads_as=(
        "Jesli slupki TRAIN i TEST sa bliskie, cecha generalizuje poza autorow "
        "treningowych. Duza luka Koran vs TEST to sygnal domeny (E-01), nie V."
    ),
    do_not_conclude=(
        "Nie wnioskuj o autorstwie Koranu. To diagnostyka F2 przed E-01. "
        "Siatka K jest w JSON-ie (100/300/1000), nie na tej osi."
    ),
)


def make_fig_41(payload: dict[str, Any], *, top_k: int = 20) -> tuple[Figure, dict[str, object]]:
    apply_style()
    names = list(payload.get("feature_names") or [])
    train = np.asarray(payload.get("mean_ctrl_train") or [], dtype=float)
    test = np.asarray(payload.get("mean_ctrl_test") or [], dtype=float)
    quran = np.asarray(payload.get("mean_quran") or [], dtype=float)
    if len(names) == 0 or train.size != len(names):
        raise ValueError("FIG-41: puste albo niespojnie cechy")
    k = min(int(top_k), len(names))
    order = np.argsort(train)[::-1][:k]
    labels = [names[int(i)] for i in order]
    y = np.arange(k)
    h = 0.28
    fig, ax = plt.subplots(figsize=(8.0, max(4.0, 0.32 * k + 1.8)))
    ax.barh(y + h, train[order], height=h, color=role_color("single"), label="ctrl_train")
    ax.barh(y, test[order], height=h, color=role_color("shuffle"), label="ctrl_test")
    ax.barh(y - h, quran[order], height=h, color=role_color("quran"), label="quran")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontfamily="DejaVu Sans")
    ax.set_xlabel("średnia częstość względna")
    ax.set_title(f"FIG-41 — T-022 F2 top function words (K={payload.get('k', '?')})")
    ax.invert_yaxis()
    ax.legend(loc="lower right")
    data: dict[str, object] = {
        "top_features": labels,
        "mean_ctrl_train": train[order].tolist(),
        "mean_ctrl_test": test[order].tolist(),
        "mean_quran": quran[order].tolist(),
        "k": payload.get("k"),
        "control": "ctrl_test_unseen_authors",
    }
    return fig, data


def save_fig_41(
    payload: dict[str, Any],
    *,
    config_hash: str | None = None,
    out_dir: Path = FIGURES_DIR,
    index_path: Path = FIGURES_INDEX_PATH,
) -> SavedFigure:
    fig, data = make_fig_41(payload)
    return save_fig(
        fig, SPEC, data, config_hash=config_hash, out_dir=out_dir, index_path=index_path
    )
