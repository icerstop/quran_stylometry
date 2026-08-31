"""T-018: zgodnosc uporzadkowan chronologicznych (docs/03_DATA.md §8).

Kolumny z ``chronologies.csv``: canonical / traditional / noldeke.
``order_sadeghi`` nie istnieje (09_DECISIONS.md §2.4, paywall).

Kotwica G9: Spearman ρ kanonicznego porządku wobec *permutacji* rang
tradycyjnych (oczekiwane ~0). ρ(traditional, noldeke) ~ 1 nie jest kontrolą
— to bliskosc dwoch prawie identycznych list.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from scipy.stats import spearmanr

from src.paths import CHRONOLOGIES_PATH, CHRONOLOGY_AGREEMENT_PATH
from src.utils.io import write_json
from src.utils.seed import new_rng

ORDER_COLUMNS: tuple[tuple[str, str], ...] = (
    ("order_canonical", "canonical"),
    ("order_traditional", "traditional"),
    ("order_noldeke", "noldeke"),
)

N_SHUFFLE = 200


def load_chronologies_table(path: Path = CHRONOLOGIES_PATH) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Brak {path} (T-018 — plik dostarczony w repo)")
    frame = pd.read_csv(path)
    missing = [col for col, _label in ORDER_COLUMNS if col not in frame.columns]
    if missing:
        raise ValueError(f"{path}: brak kolumn {missing}")
    if "order_sadeghi" in frame.columns:
        raise ValueError("order_sadeghi nie nalezy do designu (09_DECISIONS.md §2.4)")
    return frame


def spearman_matrix(frame: pd.DataFrame) -> tuple[list[str], list[list[float]]]:
    labels = [label for _col, label in ORDER_COLUMNS]
    cols = [col for col, _label in ORDER_COLUMNS]
    matrix: list[list[float]] = []
    for left in cols:
        row: list[float] = []
        for right in cols:
            rho = float(spearmanr(frame[left], frame[right]).correlation)
            row.append(rho)
        matrix.append(row)
    return labels, matrix


def rank_disagreements(frame: pd.DataFrame, left: str, right: str) -> list[int]:
    mask = frame[left] != frame[right]
    return [int(sid) for sid in frame.loc[mask, "surah_id"].tolist()]


def shuffle_spearman(
    frame: pd.DataFrame,
    *,
    seed: int,
    n_perm: int = N_SHUFFLE,
) -> dict[str, float | int]:
    """ρ(canonical, permute(traditional)) — kotwica: losowa permutacja rang."""
    canonical = frame["order_canonical"].to_numpy()
    traditional = frame["order_traditional"].to_numpy()
    rng = new_rng(seed, "t018_shuffle")
    rhos: list[float] = []
    for _ in range(int(n_perm)):
        shuffled = rng.permutation(traditional)
        rhos.append(float(spearmanr(canonical, shuffled).correlation))
    mean = float(sum(rhos) / len(rhos)) if rhos else 0.0
    if len(rhos) >= 2:
        var = sum((x - mean) ** 2 for x in rhos) / (len(rhos) - 1)
        std = var**0.5
    else:
        std = 0.0
    return {
        "n_perm": int(n_perm),
        "rho_mean": mean,
        "rho_std": float(std),
        "rho_min": min(rhos) if rhos else 0.0,
        "rho_max": max(rhos) if rhos else 0.0,
    }


def run_chronology_agreement(
    *,
    seed: int,
    path: Path = CHRONOLOGIES_PATH,
    n_perm: int = N_SHUFFLE,
) -> dict[str, Any]:
    frame = load_chronologies_table(path)
    labels, matrix = spearman_matrix(frame)
    pair_index = {label: i for i, label in enumerate(labels)}
    trad_noldeke = matrix[pair_index["traditional"]][pair_index["noldeke"]]
    canon_trad = matrix[pair_index["canonical"]][pair_index["traditional"]]
    differ = rank_disagreements(frame, "order_traditional", "order_noldeke")
    n_exc = sum(1 for val in frame["exception_verses"].tolist() if str(val or "").strip() and str(val).lower() != "nan")
    return {
        "task": "T-018",
        "n_surahs": int(len(frame)),
        "n_meccan": int((frame["period_traditional"] == "meccan").sum()),
        "n_medinan": int((frame["period_traditional"] == "medinan").sum()),
        "n_exception_verse_rows": n_exc,
        "labels": labels,
        "spearman_rho": matrix,
        "rho_traditional_noldeke": trad_noldeke,
        "rho_canonical_traditional": canon_trad,
        "n_rank_disagree_traditional_noldeke": len(differ),
        "surah_ids_disagree_traditional_noldeke": differ,
        "shuffle": shuffle_spearman(frame, seed=seed, n_perm=n_perm),
        "order_sadeghi": None,
        "note": (
            "Sadeghi (Arabica 58) i Blachere za paywallem — nie ma trzeciej "
            "niezaleznej chronologii. rho(traditional, noldeke) ~ 1 to dwa "
            "edits Tanzila, nie wrazliwosc. Kontrast: canonical vs traditional. "
            "Kontrola G9: shuffle rang traditional."
        ),
    }


def write_chronology_report(
    payload: dict[str, Any],
    *,
    path: Path = CHRONOLOGY_AGREEMENT_PATH,
    config_hash: str | None = None,
) -> Path:
    out = dict(payload)
    out["config_hash"] = config_hash
    write_json(path, out)
    return path
