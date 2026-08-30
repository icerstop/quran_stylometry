"""FIG-00 — figura testowa dla `make figs-smoke` (T-008 DoD).

Nie niesie zadnego wyniku badawczego. Istnieje po to, zeby udowodnic, ze cala
sciezka zapisu dziala: styl, komplet PNG/SVG/JSON, wpis w INDEX.md i egzekwowanie
G9. Dane sa jawnie syntetyczne i wygenerowane z seeda z configu — nie dotykaja
zadnego korpusu, wiec nie lamia zakazu liczenia czegokolwiek na Koranie przed
FREEZE (AGENTS.md zasada 2).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from src.config import Config
from src.paths import FIGURES_DIR, FIGURES_INDEX_PATH
from src.utils.seed import new_rng
from src.viz.save import FigureSpec, SavedFigure, save_fig
from src.viz.style import apply_style, role_color

SPEC = FigureSpec(
    fig_id="FIG-00",
    slug="smoke_test",
    experiment="none",
    kind="result",
    families=["synthetic"],
    control_anchor="synthetic_shuffle (rozklad odniesienia w tym samym panelu)",
    shows=(
        "Figura testowa warstwy src/viz: dwa syntetyczne rozklady i pionowa linia "
        "obserwacji, w ukladzie identycznym jak FIG-15/FIG-16."
    ),
    reads_as=(
        "Sprawdz, ze istnieja PNG, SVG i JSON o tym samym rdzeniu nazwy, oraz ten wpis "
        "w INDEX.md. Nie odczytuj z niej niczego o korpusach."
    ),
    do_not_conclude=(
        "Nie wolno wyciagac z niej ZADNEGO wniosku merytorycznego. Dane sa losowe, "
        "wygenerowane z seeda configu, i nie pochodza z zadnego korpusu."
    ),
)


def make_fig_00(config: Config) -> tuple[Figure, dict[str, object]]:
    apply_style()
    rng = new_rng(config.seed, stream="figs_smoke")

    reference = rng.normal(loc=0.40, scale=0.06, size=400)
    anchor = rng.normal(loc=0.62, scale=0.08, size=400)
    observed = float(np.median(reference) + 0.05)

    fig, ax = plt.subplots()
    bins = np.linspace(0.15, 0.9, 40).tolist()
    ax.hist(
        reference,
        bins=bins,
        alpha=0.7,
        label="rozklad odniesienia (syntetyczny)",
        color=role_color("single"),
    )
    ax.hist(
        anchor,
        bins=bins,
        alpha=0.7,
        label="kotwica kontrolna (syntetyczna)",
        color=role_color("mixture"),
    )
    ax.axvline(
        observed,
        linestyle="--",
        linewidth=2,
        label="obserwacja (syntetyczna)",
        color=role_color("quran"),
    )

    ax.set_xlabel("wartosc syntetyczna (bez jednostki)")
    ax.set_ylabel("liczba losowan")
    ax.set_title("FIG-00 — figura testowa warstwy viz (bez tresci badawczej)")
    ax.legend(loc="upper right")

    data: dict[str, object] = {
        "note": "Dane syntetyczne. Zadnej tresci badawczej.",
        "seed": config.seed,
        "stream": "figs_smoke",
        "n_reference": int(reference.size),
        "n_anchor": int(anchor.size),
        "observed": observed,
        "reference_summary": _summary(reference),
        "anchor_summary": _summary(anchor),
    }
    return fig, data


def _summary(values: np.ndarray) -> dict[str, float]:
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p05": float(np.percentile(values, 5)),
        "p95": float(np.percentile(values, 95)),
    }


def run(
    config: Config,
    *,
    out_dir: Path = FIGURES_DIR,
    index_path: Path = FIGURES_INDEX_PATH,
) -> SavedFigure:
    fig, data = make_fig_00(config)
    return save_fig(
        fig,
        SPEC,
        data,
        config_hash=config.config_hash(),
        out_dir=out_dir,
        index_path=index_path,
    )
