"""Segmentacja na okna — docs/03_DATA.md §7, guardrail G3. Implementacja: T-019.

Szkielet w P0. Reguly ogonow (`min_tail_ratio`, `max_window_ratio`) sa zamrozone
w `configs/base.yaml`, wiec testy moga juz teraz odwolywac sie do konkretnych liczb.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Wymaga src/data/segment.py — zadanie T-019 (P2)")


def test_window_never_crosses_surah_boundary() -> None:
    """G3 — okno nie przekracza granicy sury ani dziela."""
    raise NotImplementedError("T-019")


def test_short_tail_is_merged_when_above_min_ratio() -> None:
    """Ogon >= 0.6 * window_size laczy sie z poprzednim oknem..."""
    raise NotImplementedError("T-019")


def test_merged_window_never_exceeds_max_ratio() -> None:
    """...ale wynik nie moze przekroczyc 1.6 * window_size."""
    raise NotImplementedError("T-019")


def test_short_surah_becomes_composite_window() -> None:
    """Sury krotsze niz okno lacza sie w okno kompozytowe z `composite=true`."""
    raise NotImplementedError("T-019")


def test_composite_window_records_all_source_surahs() -> None:
    """Bez pelnej listy `surah_ids` nie da sie potem zrobic analizy wrazliwosci."""
    raise NotImplementedError("T-019")


def test_main_windows_have_no_overlap() -> None:
    """overlap_main = 0. Overlap 0.5 sluzy WYLACZNIE wykresom lokalnym i CPD,
    nigdy testom istotnosci — inaczej niezaleznosc obserwacji jest pozorna."""
    raise NotImplementedError("T-019")


def test_window_length_distribution_is_matched_across_corpora() -> None:
    """G6 — rozklad dlugosci okien musi byc dopasowany miedzy korpusami."""
    raise NotImplementedError("T-019")
