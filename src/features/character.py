"""T-021: F1 character n-grams (char_wb 3-5, TF-IDF), fit tylko CTRL-TRAIN."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse

from src.config import Config
from src.data.normalize_arabic import strip_diacritics_and_ligatures
from src.features.base import (
    TRAIN_SPLIT,
    fit_vectorizer,
    make_char_tfidf,
    n_zero_rows,
    nan_inf_count,
    norm_token_correlation,
    persist_vectorizer,
    row_l2_norms,
    transform_vectorizer,
)
from src.paths import (
    CHARACTER_REPORT_PATH,
    DATA_FEATURES_DIR,
    VECTORIZERS_DIR,
    rel_to_repo,
    windows_dir,
)
from src.schemas import FeatureMatrix
from src.utils.io import ensure_dir, write_json

WINDOW_COLS = ["document_id", "corpus", "split", "text_norm_strict", "n_tokens"]
MAIN_WINDOW_SIZE = 400
NORM_R_MAX = 0.3


def load_windows_frame(
    *,
    window_size: int = MAIN_WINDOW_SIZE,
    processed_dir: Path | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    folder = (
        Path(processed_dir) / f"windows_{window_size}"
        if processed_dir is not None
        else windows_dir(window_size)
    )
    ctrl_path = folder / "ctrl.parquet"
    quran_path = folder / "quran.parquet"
    if not ctrl_path.is_file():
        raise FileNotFoundError(f"Brak {ctrl_path} (T-019/T-020)")
    frames = [pd.read_parquet(ctrl_path, columns=WINDOW_COLS)]
    if quran_path.is_file():
        frames.append(pd.read_parquet(quran_path, columns=WINDOW_COLS))
    frame = pd.concat(frames, ignore_index=True)
    if limit is not None:
        frame = frame.iloc[: int(limit)].copy()
    return frame.reset_index(drop=True)


def prepare_texts(frame: pd.DataFrame, *, variant: str) -> list[str]:
    texts = [str(t or "") for t in frame["text_norm_strict"].tolist()]
    if variant == "main":
        return texts
    if variant == "no_diacritics_no_ligatures":
        return [strip_diacritics_and_ligatures(t) for t in texts]
    raise ValueError(f"Nieznany wariant F1: {variant}")


def _family_dir(config_hash: str, variant: str, *, root: Path = DATA_FEATURES_DIR) -> Path:
    return root / "character" / config_hash / variant


def save_sparse_matrix(
    matrix: sparse.spmatrix,
    index: pd.DataFrame,
    *,
    directory: Path,
    extra_meta: dict[str, Any],
    feature_names: Sequence[str],
) -> Path:
    ensure_dir(directory)
    csr = sparse.csr_matrix(matrix)
    sparse.save_npz(directory / "matrix.npz", csr)
    index.to_parquet(directory / "index.parquet", index=False)
    write_json(directory / "feature_names.json", list(feature_names))
    meta = {
        "n_rows": int(csr.shape[0]),
        "n_cols": int(csr.shape[1]),
        "nnz": int(csr.nnz),
        **extra_meta,
    }
    write_json(directory / "meta.json", meta)
    return directory


def extract_variant(
    frame: pd.DataFrame,
    *,
    variant: str,
    config: Config,
    vectorizer_dir: Path,
    features_root: Path,
    min_df: int | None = None,
    max_features: int | None = None,
) -> dict[str, Any]:
    train_mask = frame["split"].astype(str) == TRAIN_SPLIT
    train = frame.loc[train_mask]
    if train.empty:
        raise ValueError("Brak okien ctrl_train — uruchom T-020")
    train_texts = prepare_texts(train, variant=variant)
    vectorizer = make_char_tfidf(
        ngram_range=(config.features.char_ngram_range[0], config.features.char_ngram_range[1]),
        min_df=int(min_df if min_df is not None else config.features.char_min_df),
        max_features=int(max_features if max_features is not None else config.features.char_max_features),
    )
    fit_vectorizer(vectorizer, train_texts, train["split"].astype(str).tolist())
    vocab_before = dict(vectorizer.vocabulary_)
    all_texts = prepare_texts(frame, variant=variant)
    matrix = transform_vectorizer(vectorizer, all_texts)
    if dict(vectorizer.vocabulary_) != vocab_before:
        raise AssertionError("G4: slownik urosl przy transform")
    names = [str(n) for n in vectorizer.get_feature_names_out().tolist()]
    index = frame[["document_id", "corpus", "split", "n_tokens"]].copy()
    index["variant"] = variant
    norms = row_l2_norms(matrix)
    corr = norm_token_correlation(norms, index["n_tokens"].tolist())
    if abs(float(corr["r"])) >= NORM_R_MAX:
        raise AssertionError(
            f"norma wektora koreluje z n_tokens r={corr['r']:.3f} (>= {NORM_R_MAX})"
        )
    n_nan = nan_inf_count(matrix)
    n_zero = n_zero_rows(matrix)
    if n_nan:
        raise AssertionError(f"NaN/inf w macierzy F1: {n_nan}")
    if n_zero:
        raise AssertionError(f"zerowe wektory F1: {n_zero}")

    FeatureMatrix(
        family="character",
        config_label="CHARACTER",
        status="core",
        corpus_scope="cross_corpus",
        annotation_source="predicted",
        fitted_on="ctrl_train",
        config_hash=config.config_hash(),
        normalizer_version=f"{config.normalizer.profile}-{config.normalizer.version}",
        tagger_version=config.tagger.version,
        n_rows=int(matrix.shape[0]),
        n_cols=int(matrix.shape[1]),
        document_ids=index["document_id"].astype(str).tolist(),
        distance_main="cosine_delta",
    )
    vec_path = persist_vectorizer(
        vectorizer,
        family="character",
        config_hash=config.config_hash(),
        variant=variant,
        out_dir=vectorizer_dir,
    )
    out_dir = save_sparse_matrix(
        matrix,
        index,
        directory=_family_dir(config.config_hash(), variant, root=features_root),
        feature_names=names,
        extra_meta={
            "family": "character",
            "variant": variant,
            "config_hash": config.config_hash(),
            "fitted_on": TRAIN_SPLIT,
            "analyzer": "char_wb",
            "ngram_range": list(config.features.char_ngram_range),
            "vectorizer": rel_to_repo(vec_path),
            "n_train": int(train_mask.sum()),
            "norm_token_r": corr["r"],
            "norm_token_note": corr["note"],
        },
    )
    return {
        "variant": variant,
        "n_rows": int(matrix.shape[0]),
        "n_cols": int(matrix.shape[1]),
        "nnz": int(sparse.csr_matrix(matrix).nnz),
        "n_train": int(train_mask.sum()),
        "n_zero_rows": n_zero,
        "n_nan_inf": n_nan,
        "norm_token": corr,
        "vectorizer": rel_to_repo(vec_path),
        "dir": rel_to_repo(out_dir),
        "feature_names": names,
        "matrix": matrix,
        "index": index,
    }


def mean_by_mask(matrix: sparse.spmatrix, mask: np.ndarray) -> np.ndarray:
    sub = matrix[np.asarray(mask)]
    if sub.shape[0] == 0:
        return np.zeros(matrix.shape[1], dtype=float)
    return np.asarray(sub.mean(axis=0)).ravel()


def run_character_features(
    config: Config,
    *,
    window_size: int = MAIN_WINDOW_SIZE,
    processed_dir: Path | None = None,
    features_root: Path = DATA_FEATURES_DIR,
    vectorizer_dir: Path = VECTORIZERS_DIR,
    limit: int | None = None,
    skip_fig: bool = False,
    min_df: int | None = None,
    max_features: int | None = None,
) -> dict[str, Any]:
    frame = load_windows_frame(
        window_size=window_size, processed_dir=processed_dir, limit=limit
    )
    variants = ["main", "no_diacritics_no_ligatures"]
    results: dict[str, Any] = {}
    main_payload: dict[str, Any] | None = None
    for variant in variants:
        payload = extract_variant(
            frame,
            variant=variant,
            config=config,
            vectorizer_dir=vectorizer_dir,
            features_root=features_root,
            min_df=min_df,
            max_features=max_features,
        )
        results[variant] = {k: v for k, v in payload.items() if k not in {"matrix", "index", "feature_names"}}
        results[variant]["n_features_named"] = len(payload["feature_names"])
        if variant == "main":
            main_payload = payload

    assert main_payload is not None
    matrix = main_payload["matrix"]
    index = main_payload["index"]
    names = main_payload["feature_names"]
    train_m = (index["split"].astype(str) == TRAIN_SPLIT).to_numpy()
    test_m = (index["split"].astype(str) == "ctrl_test").to_numpy()
    quran_m = (index["corpus"].astype(str) == "quran").to_numpy()
    fig_data = {
        "feature_names": names,
        "mean_ctrl_train": mean_by_mask(matrix, train_m).tolist(),
        "mean_ctrl_test": mean_by_mask(matrix, test_m).tolist(),
        "mean_quran": mean_by_mask(matrix, quran_m).tolist(),
    }
    figure_path = None
    if not skip_fig:
        from src.viz.fig40_character import save_fig_40

        saved = save_fig_40(fig_data, config_hash=config.config_hash())
        figure_path = rel_to_repo(saved.png)

    return {
        "task": "T-021",
        "family": "character",
        "window_size": window_size,
        "config_hash": config.config_hash(),
        "variants": {k: v for k, v in results.items()},
        "n_windows": int(len(frame)),
        "n_ctrl_train": int((frame["split"].astype(str) == TRAIN_SPLIT).sum()),
        "n_ctrl_test": int((frame["split"].astype(str) == "ctrl_test").sum()),
        "n_quran": int((frame["corpus"].astype(str) == "quran").sum()),
        "figure": figure_path,
        "note": (
            "Fit TfidfVectorizer(char_wb, 3-5) wylacznie na CTRL-TRAIN. "
            "E-01 domain probe to T-029, nie T-021."
        ),
        "_fig_data": fig_data,
    }


def write_character_report(
    payload: dict[str, Any],
    *,
    path: Path = CHARACTER_REPORT_PATH,
    config_hash: str | None = None,
) -> Path:
    out = {k: v for k, v in payload.items() if not str(k).startswith("_")}
    if config_hash:
        out["config_hash"] = config_hash
    write_json(path, out)
    return path
