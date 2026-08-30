"""Determinizm (T-004).

`PYTHONHASHSEED` musi byc ustawiony *przed* startem interpretera, wiec kod moze
go tylko zweryfikowac i zaraportowac, nie naprawic. Dlatego `set_all_seeds`
zwraca raport, ktory trafia do metadanych artefaktu — brak determinizmu ma byc
widoczny w wynikach, a nie ukryty.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from typing import Any

import numpy as np

PYTHONHASHSEED_EXPECTED = "0"


@dataclass(frozen=True)
class SeedReport:
    """Co faktycznie udalo sie zdeterminizowac w tym procesie."""

    seed: int
    pythonhashseed: str | None
    pythonhashseed_ok: bool
    libraries: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "pythonhashseed": self.pythonhashseed,
            "pythonhashseed_ok": self.pythonhashseed_ok,
            "libraries": dict(self.libraries),
        }


def set_all_seeds(seed: int, *, deterministic_torch: bool = True) -> SeedReport:
    """Ustawia seedy dla `random`, `numpy` i — jesli obecny — `torch`.

    torch importowany leniwie: rdzen projektu nie ma go w zaleznosciach, a
    `make setup` musi przechodzic bez ekstry `nlp`.
    """
    if seed < 0:
        raise ValueError(f"Seed musi byc nieujemny, dostano {seed}")

    random.seed(seed)
    np.random.seed(seed)

    libraries: dict[str, str] = {"random": "seeded", "numpy": "seeded"}
    libraries["torch"] = _seed_torch(seed, deterministic=deterministic_torch)

    observed = os.environ.get("PYTHONHASHSEED")
    return SeedReport(
        seed=seed,
        pythonhashseed=observed,
        pythonhashseed_ok=observed == PYTHONHASHSEED_EXPECTED,
        libraries=libraries,
    )


def _seed_torch(seed: int, *, deterministic: bool) -> str:
    try:
        import torch
    except ImportError:
        return "absent"

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if deterministic:
        torch.use_deterministic_algorithms(True, warn_only=True)
    return "seeded"


def new_rng(seed: int, stream: str = "") -> np.random.Generator:
    """Niezalezny strumien losowy wyprowadzony z seeda glownego.

    Uzywanie osobnego strumienia na etap (bootstrap, permutacje, mixture) sprawia,
    ze dolozenie nowego etapu nie przesuwa losowan w etapach juz policzonych.
    """
    entropy = [seed, *(ord(ch) for ch in stream)]
    return np.random.default_rng(np.random.SeedSequence(entropy))
