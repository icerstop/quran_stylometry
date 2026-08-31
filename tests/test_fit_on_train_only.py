"""G4 — wektoryzatory i skalery fitowane wylacznie na CTRL-TRAIN (T-021)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from sklearn.feature_extraction.text import TfidfVectorizer

from src.features.base import (
    fit_standard_scaler,
    fit_vectorizer,
    make_char_tfidf,
    n_zero_rows,
    nan_inf_count,
    norm_token_correlation,
    persist_vectorizer,
    row_l2_norms,
    transform_vectorizer,
)
from src.schemas import GuardrailViolationError

TRAIN_TEXTS = [
    "aaa bbb ccc aaa bbb",
    "aaa ccc ddd aaa",
    "bbb ccc eee bbb ccc",
    "aaa bbb fff aaa",
    "ccc ddd aaa bbb ccc",
    "aaa eee bbb aaa",
]
TRAIN_SPLITS = ["ctrl_train"] * len(TRAIN_TEXTS)
QURAN_TEXTS = ["aaa bbb quran window text aaa"]


def test_vectorizer_is_fitted_only_on_ctrl_train() -> None:
    vectorizer = make_char_tfidf(min_df=1, max_features=200)
    fit_vectorizer(vectorizer, TRAIN_TEXTS, TRAIN_SPLITS)
    train_x = transform_vectorizer(vectorizer, TRAIN_TEXTS)
    quran_x = transform_vectorizer(vectorizer, QURAN_TEXTS)
    assert train_x.shape[1] == quran_x.shape[1]
    assert vectorizer.analyzer == "char_wb"


def test_fitting_on_quran_raises() -> None:
    vectorizer = make_char_tfidf(min_df=1, max_features=50)
    with pytest.raises(GuardrailViolationError, match="G4"):
        fit_vectorizer(vectorizer, QURAN_TEXTS, ["target"])
    with pytest.raises(GuardrailViolationError, match="G4"):
        fit_vectorizer(vectorizer, TRAIN_TEXTS + QURAN_TEXTS, TRAIN_SPLITS + ["target"])


def test_vocabulary_does_not_grow_on_transform() -> None:
    vectorizer = make_char_tfidf(min_df=1, max_features=200)
    fit_vectorizer(vectorizer, TRAIN_TEXTS, TRAIN_SPLITS)
    before = dict(vectorizer.vocabulary_)
    transform_vectorizer(vectorizer, QURAN_TEXTS + ["zzzz unseen zzzz"])
    assert dict(vectorizer.vocabulary_) == before


def test_scaler_statistics_come_from_ctrl_train() -> None:
    matrix = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    scaler = fit_standard_scaler(matrix, ["ctrl_train"] * 3)
    np.testing.assert_allclose(scaler.mean_, matrix.mean(axis=0))
    with pytest.raises(GuardrailViolationError, match="G4"):
        fit_standard_scaler(matrix, ["ctrl_test"] * 3)


def test_vectorizer_is_persisted_with_config_hash(tmp_path: Path) -> None:
    vectorizer = make_char_tfidf(min_df=1, max_features=80)
    fit_vectorizer(vectorizer, TRAIN_TEXTS, TRAIN_SPLITS)
    path = persist_vectorizer(
        vectorizer,
        family="character",
        config_hash="abc123",
        variant="main",
        out_dir=tmp_path,
    )
    assert path.name == "character_main_abc123.joblib"
    assert path.is_file()
    loaded = __import__("joblib").load(path)
    assert isinstance(loaded, TfidfVectorizer)
    assert loaded.vocabulary_ == vectorizer.vocabulary_


def test_matrix_has_no_nan_or_inf() -> None:
    vectorizer = make_char_tfidf(min_df=1, max_features=200)
    fit_vectorizer(vectorizer, TRAIN_TEXTS, TRAIN_SPLITS)
    matrix = transform_vectorizer(vectorizer, TRAIN_TEXTS + QURAN_TEXTS)
    assert nan_inf_count(matrix) == 0
    assert n_zero_rows(matrix) == 0


def test_vector_norm_does_not_correlate_with_n_tokens() -> None:
    vectorizer = make_char_tfidf(min_df=1, max_features=200)
    fit_vectorizer(vectorizer, TRAIN_TEXTS, TRAIN_SPLITS)
    matrix = transform_vectorizer(vectorizer, TRAIN_TEXTS)
    norms = row_l2_norms(matrix)
    n_tokens = [len(t.split()) for t in TRAIN_TEXTS]
    stats = norm_token_correlation(norms, n_tokens)
    assert abs(float(stats["r"])) < 0.3
