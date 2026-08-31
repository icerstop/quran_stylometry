"""FIG-06b — Spearman ρ między uporządkowaniami chronologicznymi (T-018).

Kotwica G9: średnie ρ kanonicznego porządku wobec permutacji rang
tradycyjnych. Sadeghi nie wchodzi na figurę (paywall).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from src.paths import FIGURES_DIR, FIGURES_INDEX_PATH
from src.viz.save import FigureSpec, SavedFigure, save_fig
from src.viz.style import DIVERGING_CMAP, apply_style

SPEC = FigureSpec(
    fig_id="FIG-06b",
    slug="chronology_agreement",
    experiment="T-018",
    kind="result",
    families=["chronology"],
    control_anchor=(
        "shuffle: Spearman ρ(order_canonical, permutacja order_traditional); "
        "n_perm i momenty w JSON. Oczekiwane ~0."
    ),
    shows=(
        "Macierz Spearman ρ: order_canonical, order_traditional, order_noldeke "
        "(114 sur). Sadeghi nieobecny."
    ),
    reads_as=(
        "ρ(traditional, noldeke) bliskie 1: dwie edycje Tanzila, nie niezależna "
        "chronologia. Kontrast to canonical vs traditional. Shuffle ~0 pokazuje, "
        "że wysokie ρ nie wynika z samego faktu, że obie listy mają 114 rang."
    ),
    do_not_conclude=(
        "Nie wnioskuj o datowaniu sur ze stylu (F-08). Nie traktuj Nöldekego "
        "jako trzeciej niezależnej osi — Sadeghi/Blachère odpadły (paywall). "
        "FIG-06b nie jest wynikiem V."
    ),
)


def make_fig_06b(payload: dict[str, Any]) -> tuple[Figure, dict[str, object]]:
    apply_style()
    labels = list(payload.get("labels") or [])
    matrix = np.asarray(payload.get("spearman_rho") or [], dtype=float)
    if matrix.size == 0 or len(labels) != matrix.shape[0]:
        raise ValueError("FIG-06b: pusta albo niespójna macierz Spearman")
    shuffle = dict(payload.get("shuffle") or {})
    shuf_mean = float(shuffle.get("rho_mean") or 0.0)
    shuf_std = float(shuffle.get("rho_std") or 0.0)
    n_perm = int(shuffle.get("n_perm") or 0)
    n_disagree = int(payload.get("n_rank_disagree_traditional_noldeke") or 0)

    fig, ax = plt.subplots(figsize=(6.2, 5.4))
    image = ax.imshow(matrix, cmap=DIVERGING_CMAP, vmin=-1.0, vmax=1.0)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_yticklabels(labels)
    ax.set_title("FIG-06b — T-018 zgodność chronologii (Spearman ρ)")
    ax.grid(False)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            val = float(matrix[i, j])
            ax.text(
                j,
                i,
                f"{val:.3f}",
                ha="center",
                va="center",
                color="white" if abs(val) > 0.55 else "#111111",
                fontsize=10,
            )
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04, label="Spearman ρ")
    fig.subplots_adjust(bottom=0.28)
    ax.text(
        0.0,
        -0.22,
        (
            f"shuffle G9: ρ(canonical, perm(traditional)) "
            f"= {shuf_mean:.3f} ± {shuf_std:.3f} (n={n_perm}); "
            f"traditional≠noldeke: {n_disagree} sur. "
            "Sadeghi / Blachère: paywall — poza figurą."
        ),
        transform=ax.transAxes,
        fontsize=8,
        va="top",
    )

    data: dict[str, object] = {
        "labels": labels,
        "spearman_rho": matrix.tolist(),
        "shuffle_rho_mean": shuf_mean,
        "shuffle_rho_std": shuf_std,
        "n_perm": n_perm,
        "n_rank_disagree_traditional_noldeke": n_disagree,
        "control": "rank_shuffle_traditional_vs_canonical",
        "order_sadeghi": None,
    }
    return fig, data


def save_fig_06b(
    payload: dict[str, Any],
    *,
    config_hash: str | None = None,
    out_dir: Path = FIGURES_DIR,
    index_path: Path = FIGURES_INDEX_PATH,
) -> SavedFigure:
    fig, data = make_fig_06b(payload)
    return save_fig(
        fig, SPEC, data, config_hash=config_hash, out_dir=out_dir, index_path=index_path
    )
