"""Wspolny styl figur (T-008, docs/06_FIGURES.md).

Paleta zgodna z daltonizmem: Okabe-Ito dla kategorii, viridis/cividis dla map
ciepla. Czerwony i zielony nigdy nie wystepuja jako jedyny kontrast miedzy
dwiema kategoriami — dlatego kolejnosc Okabe-Ito jest tu ustalona na sztywno,
a nie przepisana z domyslnych cykli matplotliba.
"""

from __future__ import annotations

from typing import Any

import matplotlib

matplotlib.use("Agg")  # figury powstaja ze skryptu, nigdy z interaktywnego backendu

import matplotlib.style  # noqa: E402
from cycler import cycler  # noqa: E402

# Okabe-Ito. Pierwsze dwie pozycje (pomaranczowy, blekit) sa rozroznialne przy
# kazdym typie daltonizmu — to one obsluguja domyslny kontrast dwoch kategorii.
CATEGORICAL_PALETTE: tuple[str, ...] = (
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#009E73",  # bluish green
    "#F0E442",  # yellow
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#CC79A7",  # reddish purple
    "#000000",  # black
)

SEQUENTIAL_CMAP = "viridis"
DIVERGING_CMAP = "cividis"

# Role semantyczne — zeby "kotwica kontrolna" wygladala tak samo na kazdej figurze.
ROLE_COLORS: dict[str, str] = {
    "quran": "#D55E00",
    "single": "#0072B2",
    "mixture": "#E69F00",
    "multivoice": "#CC79A7",
    "floor": "#009E73",
    "baseline": "#56B4E9",
    "shuffle": "#000000",
}

_RCPARAMS: dict[str, Any] = {
    "figure.figsize": (8.0, 5.0),
    "figure.dpi": 110,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "axes.grid": True,
    "axes.axisbelow": True,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.prop_cycle": cycler(color=list(CATEGORICAL_PALETTE)),
    "grid.alpha": 0.3,
    "grid.linewidth": 0.6,
    "legend.frameon": False,
    "image.cmap": SEQUENTIAL_CMAP,
    "svg.fonttype": "none",  # tekst w SVG zostaje tekstem, nie krzywymi
}


def apply_style() -> None:
    """Nadpisuje rcParams. Idempotentna — mozna wolac na poczatku kazdej figury."""
    matplotlib.style.use(_RCPARAMS)


def role_color(role: str) -> str:
    return ROLE_COLORS.get(role, CATEGORICAL_PALETTE[0])
