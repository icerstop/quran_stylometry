"""Normalizator arabskiego — docs/03_DATA.md §4. Implementacja: T-013.

Szkielet zapisany w P0, zeby kontrakt byl widoczny, zanim powstanie kod.
Kazdy przypadek pochodzi z §4 i z listy pulapek w 07_TASKS.md (T-013).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Wymaga src/data/normalize.py — zadanie T-013 (P2)")


def test_alif_variants_collapse_in_strict_profile() -> None:
    """Profil strict: أ إ آ ٱ -> ا."""
    raise NotImplementedError("T-013")


def test_light_profile_preserves_alif_variants() -> None:
    """Profil light istnieje po to, zeby zmierzyc wplyw ujednolicenia (F-03)."""
    raise NotImplementedError("T-013")


def test_diacritics_are_removed_before_alif_unification() -> None:
    """Kolejnosc krokow jest czescia decyzji, nie szczegolem implementacji."""
    raise NotImplementedError("T-013")


def test_quranic_pause_marks_and_sajda_are_removed() -> None:
    """Znaki pauzy i sajda wystepuja tylko po stronie Koranu — zostawienie ich
    daje darmowy sygnal odrozniajacy korpusy (G2)."""
    raise NotImplementedError("T-013")


def test_normalizer_is_idempotent() -> None:
    """normalize(normalize(x)) == normalize(x)."""
    raise NotImplementedError("T-013")


def test_token_count_is_stable_under_normalization() -> None:
    """Normalizacja nie moze sklejac ani rozbijac slow ortograficznych."""
    raise NotImplementedError("T-013")


def test_dagger_alif_and_wasla_are_handled_explicitly() -> None:
    """Pulapka z T-013: alif chanjariyya (ٰ) i wasla (ٱ) w ortografii uthmani."""
    raise NotImplementedError("T-013")
