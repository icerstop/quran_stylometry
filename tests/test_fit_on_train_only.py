"""G4 — wektoryzatory i skalery fitowane wylacznie na CTRL-TRAIN.

Implementacja: T-021 (`src/features/base.py`). W P0 warstwa deklaratywna jest
juz pilnowana przez `FeatureMatrix` (patrz `test_no_gold_in_crosscorpus.py`);
te testy sprawdza zachowanie samego obiektu wektoryzatora.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Wymaga src/features/base.py — zadanie T-021 (P2)")


def test_vectorizer_is_fitted_only_on_ctrl_train() -> None:
    """Fit widzi wylacznie CTRL-TRAIN; Koran i CTRL-TEST to samo `transform`."""
    raise NotImplementedError("T-021")


def test_fitting_on_quran_raises() -> None:
    """Proba fitu na korpusie docelowym ma byc bledem, nie ostrzezeniem."""
    raise NotImplementedError("T-021")


def test_vocabulary_does_not_grow_on_transform() -> None:
    """Slownik po `transform` na Koranie musi byc identyczny jak po `fit`."""
    raise NotImplementedError("T-021")


def test_scaler_statistics_come_from_ctrl_train() -> None:
    """mu i sigma z CTRL-TRAIN; dla Delty to warunek poprawnosci z-score'ow."""
    raise NotImplementedError("T-021")


def test_vectorizer_is_persisted_with_config_hash() -> None:
    """models/vectorizers/<family>_<config_hash>.joblib — 04_FEATURES §0 pkt 1."""
    raise NotImplementedError("T-021")


def test_matrix_has_no_nan_or_inf() -> None:
    """Checklist z 04_FEATURES §12."""
    raise NotImplementedError("T-021")


def test_vector_norm_does_not_correlate_with_n_tokens() -> None:
    """r < 0.3; jesli koreluje, normalizacja jest zepsuta (04_FEATURES §12)."""
    raise NotImplementedError("T-021")
