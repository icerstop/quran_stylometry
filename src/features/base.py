"""G4: wektoryzatory i skalery fitowane wylacznie na CTRL-TRAIN."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler

from src.paths import VECTORIZERS_DIR, rel_to_repo
from src.schemas import GuardrailViolationError
from src.utils.io import ensure_dir

TRAIN_SPLIT = "ctrl_train"


def assert_ctrl_train_only(splits: Sequence[str]) -> None:
    """G4 — fit widzi wylacznie CTRL-TRAIN."""
    bad = sorted({str(s) for s in splits if str(s) != TRAIN_SPLIT})
    if bad:
        raise GuardrailViolationError(
            f"G4: proba fitu na splitach {bad}. Dozwolone jest wylacznie '{TRAIN_SPLIT}'."
        )


def make_char_tfidf(
    *,
    ngram_range: tuple[int, int] = (3, 5),
    min_df: int = 5,
    max_features: int = 50000,
    sublinear_tf: bool = True,
) -> TfidfVectorizer:
    if int(ngram_range[0]) > int(ngram_range[1]):
        raise ValueError(f"ngram_range={ngram_range}")
    return TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(int(ngram_range[0]), int(ngram_range[1])),
        min_df=min_df,
        max_features=max_features,
        sublinear_tf=sublinear_tf,
        lowercase=False,
        norm="l2",
    )


def make_lexical_tfidf(
    *,
    ngram_range: tuple[int, int] = (1, 2),
    min_df: int = 5,
    max_features: int | None = None,
    sublinear_tf: bool = True,
) -> TfidfVectorizer:
    """Word/lemma/root 1–2 gram. tokenizer=split, zeby 1-znakowe formy nie wypadly."""
    if int(ngram_range[0]) > int(ngram_range[1]):
        raise ValueError(f"ngram_range={ngram_range}")
    kwargs: dict[str, Any] = {
        "analyzer": "word",
        "ngram_range": (int(ngram_range[0]), int(ngram_range[1])),
        "min_df": min_df,
        "sublinear_tf": sublinear_tf,
        "lowercase": False,
        "tokenizer": str.split,
        "token_pattern": None,
        "norm": "l2",
    }
    if max_features is not None:
        kwargs["max_features"] = int(max_features)
    return TfidfVectorizer(**kwargs)


def fit_vectorizer(
    vectorizer: TfidfVectorizer,
    texts: Sequence[str],
    splits: Sequence[str],
) -> TfidfVectorizer:
    if len(texts) != len(splits):
        raise ValueError(f"len(texts)={len(texts)} != len(splits)={len(splits)}")
    assert_ctrl_train_only(splits)
    vectorizer.fit(list(texts))
    return vectorizer


def transform_vectorizer(vectorizer: TfidfVectorizer, texts: Sequence[str]) -> sparse.spmatrix:
    if not hasattr(vectorizer, "vocabulary_"):
        raise GuardrailViolationError("G4: transform bez uprzedniego fitu na CTRL-TRAIN")
    return vectorizer.transform(list(texts))


def persist_vectorizer(
    vectorizer: TfidfVectorizer,
    *,
    family: str,
    config_hash: str,
    variant: str = "main",
    out_dir: Path = VECTORIZERS_DIR,
) -> Path:
    ensure_dir(out_dir)
    path = out_dir / f"{family}_{variant}_{config_hash}.joblib"
    joblib.dump(vectorizer, path)
    return path


def load_vectorizer(path: Path) -> TfidfVectorizer:
    loaded = joblib.load(path)
    if not isinstance(loaded, TfidfVectorizer):
        raise TypeError(f"{path}: oczekiwano TfidfVectorizer, dostano {type(loaded)}")
    return loaded


def fit_standard_scaler(
    matrix: np.ndarray | sparse.spmatrix,
    splits: Sequence[str],
    *,
    with_mean: bool | None = None,
) -> StandardScaler:
    """mu/sigma z CTRL-TRAIN. Na macierzy sparse `with_mean` musi byc False."""
    assert_ctrl_train_only(splits)
    is_sparse = sparse.issparse(matrix)
    if with_mean is None:
        with_mean = not is_sparse
    if is_sparse and with_mean:
        raise ValueError("StandardScaler(with_mean=True) na sparse zagestylaby macierz")
    scaler = StandardScaler(with_mean=with_mean, with_std=True)
    scaler.fit(matrix)
    return scaler


def row_l2_norms(matrix: sparse.spmatrix | np.ndarray) -> np.ndarray:
    if sparse.issparse(matrix):
        squared = matrix.multiply(matrix).sum(axis=1)
        return np.sqrt(np.asarray(squared).ravel())
    arr = np.asarray(matrix, dtype=float)
    return np.linalg.norm(arr, axis=1)


def nan_inf_count(matrix: sparse.spmatrix | np.ndarray) -> int:
    if sparse.issparse(matrix):
        data = np.asarray(matrix.data, dtype=float)
        return int(np.size(data) - np.count_nonzero(np.isfinite(data)))
    arr = np.asarray(matrix, dtype=float)
    return int(np.size(arr) - np.count_nonzero(np.isfinite(arr)))


def n_zero_rows(matrix: sparse.spmatrix | np.ndarray) -> int:
    if sparse.issparse(matrix):
        return int(np.sum(np.asarray(matrix.getnnz(axis=1) == 0)))
    arr = np.asarray(matrix, dtype=float)
    return int(np.sum(np.all(arr == 0, axis=1)))


def norm_token_correlation(norms: np.ndarray, n_tokens: Sequence[int]) -> dict[str, Any]:
    norms = np.asarray(norms, dtype=float)
    tokens = np.asarray(list(n_tokens), dtype=float)
    if len(norms) != len(tokens) or len(norms) < 3:
        return {"r": 0.0, "n": int(len(norms)), "note": "za malo wierszy"}
    if float(np.std(norms)) < 1e-12:
        return {
            "r": 0.0,
            "n": int(len(norms)),
            "note": "normy stale (L2 TF-IDF) — brak korelacji z n_tokens",
        }
    r = float(np.corrcoef(norms, tokens)[0, 1])
    if not np.isfinite(r):
        r = 0.0
    return {"r": r, "n": int(len(norms)), "note": ""}


def vectorizer_relpath(path: Path) -> str:
    return rel_to_repo(path)
