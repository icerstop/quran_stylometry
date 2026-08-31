"""FIG-05 — usuwanie cytatow koranicznych per gatunek (T-016).

Kotwica G9: ten sam pipeline na 7-gramach z POTASOWANYCH tokenow Koranu
(shuffle niszczy ciaglosc cytatu). Jesli slupki shuffle sa bliskie usunieciu
z prawdziwego indeksu, detektor lapie czeste slowa, nie cytaty.
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
    fig_id="FIG-05",
    slug="quote_removal",
    experiment="T-016",
    kind="result",
    families=["quotes"],
    control_anchor=(
        "shuffle: 7-gramy z permutacji tokenow Koranu (ten sam slownik i n, "
        "bez ciaglosci cytatu); usuniecie z CTRL przy identycznym marginesie ±3"
    ),
    shows=(
        "Per gatunek CTRL: tokeny RAW, tokeny wykryte jako cytat (7-gramy), "
        "tokeny usuniete po marginesie ±3, oraz usuniecie na indeksie shuffle."
    ),
    reads_as=(
        "Wysoki slupek usunietych przy niskim shuffle znaczy, ze wycinamy "
        "ciagi z Koranu, nie losowe zbitki. Tafsir moze tracic 30–50% objetosci "
        "— to oczekiwane (03_DATA.md §7a), nie blad."
    ),
    do_not_conclude=(
        "Nie wnioskuj o autorstwie Koranu. Precyzja/recall sa z recznego audytu "
        "2×100, nie z tej figury. Shuffle to kontrola struktury, nie p-wartosc."
    ),
)


def make_fig_05(payload: dict[str, Any]) -> tuple[Figure, dict[str, object]]:
    apply_style()
    by_genre: dict[str, Any] = dict(payload.get("by_genre") or {})
    labels = sorted(by_genre, key=lambda g: -int(by_genre[g].get("tokens_raw") or 0))
    raw = [int(by_genre[g]["tokens_raw"]) for g in labels]
    detected = [int(by_genre[g].get("tokens_detected_spans") or 0) for g in labels]
    removed = [int(by_genre[g].get("tokens_removed") or 0) for g in labels]
    shuffle = [int(by_genre[g].get("tokens_shuffle_removed") or 0) for g in labels]

    fig, ax = plt.subplots(figsize=(8.0, max(3.5, 0.35 * len(labels) + 1.5)))
    y = list(range(len(labels)))
    h = 0.2
    ax.barh([v + 1.5 * h for v in y], raw, height=h, color=role_color("single"), label="RAW")
    ax.barh(
        [v + 0.5 * h for v in y],
        detected,
        height=h,
        color=role_color("quran"),
        label="wykryte (7-gram)",
    )
    ax.barh(
        [v - 0.5 * h for v in y],
        removed,
        height=h,
        color=role_color("mixture"),
        label="usuniete (±3)",
    )
    ax.barh(
        [v - 1.5 * h for v in y],
        shuffle,
        height=h,
        color=role_color("shuffle"),
        label="shuffle (kotwica)",
    )
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("tokeny")
    ax.set_title("FIG-05 — T-016 cytaty Koranu w CTRL")
    ax.legend(loc="lower right")
    ax.invert_yaxis()

    totals = payload.get("totals") or {}
    data: dict[str, object] = {
        "by_genre": by_genre,
        "totals": totals,
        "genres": labels,
        "control": "shuffle_quran_ngrams",
    }
    return fig, data


def save_fig_05(
    payload: dict[str, Any],
    *,
    config_hash: str | None = None,
    out_dir: Path = FIGURES_DIR,
    index_path: Path = FIGURES_INDEX_PATH,
) -> SavedFigure:
    fig, data = make_fig_05(payload)
    return save_fig(
        fig, SPEC, data, config_hash=config_hash, out_dir=out_dir, index_path=index_path
    )
