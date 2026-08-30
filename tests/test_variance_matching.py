"""G6 — porownania V tylko przy dopasowanym n_w i rozkladzie dlugosci okien.

Implementacja: T-035 (`src/evaluation/variance.py`).

Bez dopasowania `n_w` rozklad V_single jest wezszy albo szerszy niz V_Quran
z powodu samej liczby okien, a nie z powodu stylu — i cala skala odniesienia
przestaje cokolwiek znaczyc.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Wymaga src/evaluation/variance.py — zadanie T-035 (P5)")


def test_n_windows_is_derived_from_quran_not_hardcoded() -> None:
    """`n_windows_match: auto` — liczba okien wyliczana z Koranu (09_DECISIONS §6)."""
    raise NotImplementedError("T-035")


def test_control_corpora_are_subsampled_to_the_same_n_windows() -> None:
    raise NotImplementedError("T-035")


def test_window_length_distributions_are_matched() -> None:
    raise NotImplementedError("T-035")


def test_mismatched_n_windows_raises() -> None:
    """Porownanie przy roznym n_w ma byc bledem, nie przypisem pod figura."""
    raise NotImplementedError("T-035")


def test_all_four_anchors_are_present_before_reporting() -> None:
    """V_within-surah, V_single, V_mixture-k, V_multivoice — komplet albo nic."""
    raise NotImplementedError("T-035")


def test_both_estimators_are_computed() -> None:
    """V_med i V_disp; rozejscie sie estymatorow jest wynikiem, nie usterka."""
    raise NotImplementedError("T-035")


def test_quran_percentile_is_reported_with_bootstrap_ci() -> None:
    raise NotImplementedError("T-035")
