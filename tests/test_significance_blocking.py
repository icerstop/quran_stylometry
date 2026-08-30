"""G5 — istotnosc liczona z permutacji po autorach i surach, nigdy z par.

Implementacja: T-035 (`src/evaluation/significance.py`).

Sedno guardraila: dystanse parowe nie sa niezalezne, wiec p-wartosc policzona
tak, jakby byly, jest zawyzona o rzedy wielkosci. Blokujemy po `author_id`
(CTRL) i po `surah_id` (Koran).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Wymaga src/evaluation/significance.py — zadanie T-035 (P5)")


def test_permutation_blocks_by_author_on_ctrl() -> None:
    raise NotImplementedError("T-035")


def test_permutation_blocks_by_surah_on_quran() -> None:
    raise NotImplementedError("T-035")


def test_pairwise_distances_are_rejected_as_input_to_pvalue() -> None:
    """Proba policzenia p-wartosci wprost z dystansow parowych ma podniesc wyjatek."""
    raise NotImplementedError("T-035")


def test_permutation_count_matches_frozen_config() -> None:
    """10 000 permutacji z 09_DECISIONS §6 — liczba jest zamrozona."""
    raise NotImplementedError("T-035")


def test_bootstrap_resamples_authors_not_windows() -> None:
    """CI dla V pochodzi z bootstrapu PO AUTORACH; po oknach byloby zanizone."""
    raise NotImplementedError("T-035")


def test_pvalue_is_reported_with_effect_size() -> None:
    """02_DESIGN: sama p-wartosc bez wielkosci efektu nie jest wynikiem."""
    raise NotImplementedError("T-035")
