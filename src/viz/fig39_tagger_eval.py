"""FIG-39 — ewaluacja taggera CAMeL vs EQTB gold (T-014, diagnostyczna).

Kotwica: accuracy majority-class na warstwie coarse (zawsze przewiduj
najczestszy tag gold). To nie jest figura wynikowa cross-corpus.
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
    fig_id="FIG-39",
    slug="tagger_eval",
    experiment="T-014",
    kind="diagnostic",
    families=["pos", "morph"],
    control_anchor=(
        "majority-class baseline na warstwie coarse POS "
        "(najczestszy tag gold EQTB, ta sama liczba tokenow)"
    ),
    shows=(
        "Accuracy POS CAMeL Tools (calima-msa-r13, MLE) wobec gold EQTB "
        "per kubelek coarse, obok linii majority baseline."
    ),
    reads_as=(
        "Slupek = udzial poprawnych tagow coarse w danym kubełku. "
        "Pionowa linia = accuracy, gdyby tagger zawsze zwracal najczestszy tag gold. "
        "Fine POS i lemat sa w JSON-ie figury / results/tagger_eval.json, nie na osi."
    ),
    do_not_conclude=(
        "Nie wnioskuj z tej figury o autorstwie Koranu ani o jakosci tagowania CTRL. "
        "Referencja to EQTB (fallback T-010), nie QAC. CAMeL jest MSA, nie Quranic-specific."
    ),
)


def make_fig_39(payload: dict[str, Any]) -> tuple[Figure, dict[str, object]]:
    apply_style()
    per_coarse: dict[str, Any] = payload.get("per_pos_coarse") or {}
    labels = list(per_coarse.keys())
    acc = [float(per_coarse[k]["accuracy"]) for k in labels]
    ns = [int(per_coarse[k]["n"]) for k in labels]
    baseline = float(payload.get("metrics", {}).get("majority_baseline_coarse") or 0.0)

    fig, ax = plt.subplots()
    y = list(range(len(labels)))
    ax.barh(y, acc, color=role_color("quran"), label="CAMeL (coarse POS)")
    ax.axvline(
        baseline,
        linestyle="--",
        linewidth=2,
        color=role_color("baseline"),
        label=f"majority baseline ({baseline:.3f})",
    )
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlim(0, 1)
    ax.set_xlabel("accuracy")
    ax.set_title("FIG-39 — T-014 CAMeL vs EQTB gold (Koran, diagnostyka)")
    ax.legend(loc="lower right")
    ax.invert_yaxis()

    data: dict[str, object] = {
        "per_pos_coarse": per_coarse,
        "n_per_coarse": dict(zip(labels, ns, strict=True)),
        "majority_baseline_coarse": baseline,
        "metrics": payload.get("metrics", {}),
        "reference_corpus": payload.get("reference_corpus"),
        "n_words": payload.get("n_words"),
    }
    return fig, data


def run(
    payload: dict[str, Any],
    *,
    config_hash: str | None = None,
    out_dir: Path = FIGURES_DIR,
    index_path: Path = FIGURES_INDEX_PATH,
) -> SavedFigure:
    fig, data = make_fig_39(payload)
    return save_fig(
        fig,
        SPEC,
        data,
        config_hash=config_hash,
        out_dir=out_dir,
        index_path=index_path,
    )
