"""T-023: F3 lexical TF-IDF (word / lemma / root 1-2 gram), fit tylko CTRL-TRAIN.

Status: support — gorna granica topic leakage, nie wniosek glowny.
Rdzenie z taggera (*_pred), nigdy root_ar z EQTB (G1).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse

from src.annotate.gold import normalize_lemma
from src.annotate.tagger import analysis_mapping
from src.config import Config
from src.data.segment import cut_unit
from src.features.base import (
    TRAIN_SPLIT,
    fit_vectorizer,
    make_lexical_tfidf,
    n_zero_rows,
    nan_inf_count,
    norm_token_correlation,
    persist_vectorizer,
    row_l2_norms,
    transform_vectorizer,
)
from src.features.character import load_windows_frame, mean_by_mask, save_sparse_matrix
from src.features.function_words import (
    align_ctrl_book_tags,
    find_token_span,
    load_feature_index,
    tag_quran_predicted,
)
from src.paths import (
    CTRL_TAGGED_DIR,
    DATA_FEATURES_DIR,
    LEXICAL_REPORT_PATH,
    OPENITI_CLEAN_DIR,
    QURAN_TAGGED_PATH,
    VECTORIZERS_DIR,
    rel_to_repo,
)
from src.schemas import FeatureMatrix
from src.utils.io import write_json

FAMILY = "lexical"
UNITS: tuple[str, ...] = ("word", "lemma", "root")
NGRAM_RANGE = (1, 2)
MIN_DF = 5
NORM_R_MAX = 0.3
MAIN_WINDOW_SIZE = 400
MAIN_UNIT = "word"
EMPTY_MARKERS = frozenset({"", "nan", "none", "_", "na"})


def join_field(values: Sequence[Any]) -> str:
    parts: list[str] = []
    for raw in values:
        text = str(raw or "").strip()
        if text.lower() in EMPTY_MARKERS:
            continue
        parts.append(text)
    return " ".join(parts)


def make_analyzer(database: str = "calima-msa-r13") -> Any | None:
    try:
        from camel_tools.morphology.analyzer import Analyzer
        from camel_tools.morphology.database import MorphologyDB
    except ImportError:
        return None
    try:
        db = MorphologyDB.builtin_db(database)
        return Analyzer(db)
    except Exception:
        try:
            return Analyzer(MorphologyDB.builtin_db())
        except Exception:
            return None


def lookup_root(
    token: str,
    lemma_pred: str,
    analyzer: Any,
    *,
    cache: dict[tuple[str, str], str],
    profile: str = "strict",
) -> str:
    key = (token, lemma_pred)
    if key in cache:
        return cache[key]
    root = ""
    try:
        analyses = analyzer.analyze(token) or []
    except Exception:
        analyses = []
    for item in analyses:
        mapping = analysis_mapping(item)
        lex = str(mapping.get("lex") or "")
        if normalize_lemma(lex, profile=profile) != lemma_pred:
            continue
        cand = str(mapping.get("root") or "").strip()
        if cand:
            root = cand
            break
    cache[key] = root
    return root


def attach_roots(frame: pd.DataFrame, analyzer: Any | None, cache: dict[tuple[str, str], str]) -> pd.DataFrame:
    if "root_pred" in frame.columns:
        return frame
    if analyzer is None:
        out = frame.copy()
        out["root_pred"] = ""
        return out
    roots: list[str] = []
    for rec in frame.itertuples(index=False):
        token = str(rec.token)
        lemma = str(getattr(rec, "lemma_pred", "") or "")
        roots.append(lookup_root(token, lemma, analyzer, cache=cache))
    out = frame.copy()
    out["root_pred"] = roots
    return out


def collect_ctrl_texts(
    index: pd.DataFrame,
    *,
    fields: Sequence[str],
    tagged_dir: Path,
    clean_dir: Path,
    window_size: int,
    min_tail_ratio: float,
    max_window_ratio: float,
    analyzer: Any | None,
    root_cache: dict[tuple[str, str], str],
) -> dict[str, list[str]]:
    ctrl = index.loc[index["corpus"].astype(str) == "ctrl"]
    by_doc = {str(d): i for i, d in enumerate(index["document_id"].astype(str))}
    out: dict[str, list[str | None]] = {f: [None] * len(index) for f in fields}
    versions = sorted(
        {
            str(v)
            for v in ctrl["version_id"].astype(str).tolist()
            if str(v) and str(v) not in {"nan", "None", ""}
        }
    )
    need_root = "root" in fields
    for vi, version_id in enumerate(versions):
        aligned = align_ctrl_book_tags(
            version_id=version_id, tagged_dir=tagged_dir, clean_dir=clean_dir
        )
        if need_root:
            aligned = attach_roots(aligned, analyzer, root_cache)
        n_tok = len(aligned)
        spans = cut_unit(
            n_tok,
            window_size=window_size,
            min_tail_ratio=min_tail_ratio,
            max_window_ratio=max_window_ratio,
            overlap=0.0,
        )
        for idx, (lo, hi) in enumerate(spans):
            doc = f"ctrl_{version_id}_w{idx:04d}"
            row_i = by_doc.get(doc)
            if row_i is None:
                continue
            chunk = aligned.iloc[lo:hi]
            expected_n = int(index.iloc[row_i]["n_tokens"])
            if len(chunk) != expected_n:
                raise AssertionError(f"{doc}: tagged span {len(chunk)} != n_tokens {expected_n}")
            for field in fields:
                col = "lemma_pred" if field == "lemma" else "root_pred"
                out[field][row_i] = join_field(chunk[col].tolist())
        if (vi + 1) % 50 == 0 or vi + 1 == len(versions):
            print(f"F3 ctrl books {vi + 1}/{len(versions)}", flush=True)
    for field, texts in out.items():
        missing = [
            str(index.iloc[i]["document_id"])
            for i, val in enumerate(texts)
            if val is None and str(index.iloc[i]["corpus"]) == "ctrl"
        ]
        if missing:
            raise FileNotFoundError(
                f"Brak tagow F3/{field} dla okien CTRL: {missing[:5]} (+{len(missing)})"
            )
    return {f: [t or "" for t in texts] for f, texts in out.items()}


def collect_quran_texts(
    index: pd.DataFrame,
    tokens_by_doc: dict[str, list[str]],
    *,
    fields: Sequence[str],
    quran_tagged: Path,
    analyzer: Any | None,
    root_cache: dict[tuple[str, str], str],
    tagger: Any | None = None,
) -> dict[str, list[str]]:
    out = {f: [""] * len(index) for f in fields}
    qmask = index["corpus"].astype(str) == "quran"
    if not bool(qmask.any()):
        return out
    path = tag_quran_predicted(out_path=quran_tagged, tagger=tagger)
    tagged = pd.read_parquet(path)
    if "root" in fields:
        tagged = attach_roots(tagged, analyzer, root_cache)
    stream_tokens = [str(t) for t in tagged["token"].tolist()]
    cursor = 0
    for pos in range(len(index)):
        if str(index.iloc[pos]["corpus"]) != "quran":
            continue
        doc = str(index.iloc[pos]["document_id"])
        needle = list(tokens_by_doc[doc])
        lo, hi = find_token_span(stream_tokens, needle, start=cursor)
        cursor = hi
        chunk = tagged.iloc[lo:hi]
        for field in fields:
            col = "lemma_pred" if field == "lemma" else "root_pred"
            out[field][pos] = join_field(chunk[col].tolist())
    return out


def extract_unit(
    frame: pd.DataFrame,
    texts: Sequence[str],
    *,
    unit: str,
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
    train_texts = [texts[i] for i in np.flatnonzero(train_mask.to_numpy())]
    vectorizer = make_lexical_tfidf(
        ngram_range=NGRAM_RANGE,
        min_df=int(min_df if min_df is not None else MIN_DF),
        max_features=max_features,
    )
    fit_vectorizer(vectorizer, train_texts, train["split"].astype(str).tolist())
    vocab_before = dict(vectorizer.vocabulary_)
    matrix = transform_vectorizer(vectorizer, list(texts))
    if dict(vectorizer.vocabulary_) != vocab_before:
        raise AssertionError("G4: slownik urosl przy transform")
    names = [str(n) for n in vectorizer.get_feature_names_out().tolist()]
    index = frame[["document_id", "corpus", "split", "n_tokens"]].copy()
    index["variant"] = unit
    norms = row_l2_norms(matrix)
    corr = norm_token_correlation(norms, index["n_tokens"].tolist())
    if abs(float(corr["r"])) >= NORM_R_MAX:
        raise AssertionError(
            f"norma wektora F3/{unit} koreluje z n_tokens r={corr['r']:.3f} (>= {NORM_R_MAX})"
        )
    n_nan = nan_inf_count(matrix)
    n_zero = n_zero_rows(matrix)
    if n_nan:
        raise AssertionError(f"NaN/inf w macierzy F3/{unit}: {n_nan}")
    if n_zero:
        raise AssertionError(f"zerowe wektory F3/{unit}: {n_zero}")
    FeatureMatrix(
        family=FAMILY,
        config_label="LEXICAL",
        status="support",
        corpus_scope="cross_corpus",
        annotation_source="predicted",
        fitted_on="ctrl_train",
        config_hash=config.config_hash(),
        normalizer_version=f"{config.normalizer.profile}-{config.normalizer.version}",
        tagger_version=config.tagger.version,
        n_rows=int(matrix.shape[0]),
        n_cols=int(matrix.shape[1]),
        document_ids=index["document_id"].astype(str).tolist(),
        distance_main="cosine",
    )
    vec_path = persist_vectorizer(
        vectorizer,
        family=FAMILY,
        config_hash=config.config_hash(),
        variant=unit,
        out_dir=vectorizer_dir,
    )
    out_dir = save_sparse_matrix(
        matrix,
        index,
        directory=features_root / FAMILY / config.config_hash() / unit,
        feature_names=names,
        extra_meta={
            "family": FAMILY,
            "variant": unit,
            "config_hash": config.config_hash(),
            "fitted_on": TRAIN_SPLIT,
            "ngram_range": list(NGRAM_RANGE),
            "min_df": int(min_df if min_df is not None else MIN_DF),
            "vectorizer": rel_to_repo(vec_path),
            "n_train": int(train_mask.sum()),
            "norm_token_r": corr["r"],
            "annotation_source": "predicted",
            "status": "support",
        },
    )
    n_empty = sum(1 for t in texts if not t)
    return {
        "variant": unit,
        "n_rows": int(matrix.shape[0]),
        "n_cols": int(matrix.shape[1]),
        "nnz": int(sparse.csr_matrix(matrix).nnz),
        "n_train": int(train_mask.sum()),
        "n_zero_rows": n_zero,
        "n_nan_inf": n_nan,
        "n_empty_docs": n_empty,
        "norm_token": corr,
        "vectorizer": rel_to_repo(vec_path),
        "dir": rel_to_repo(out_dir),
        "feature_names": names,
        "matrix": matrix,
        "index": index,
    }


def run_lexical_features(
    config: Config,
    *,
    window_size: int = MAIN_WINDOW_SIZE,
    processed_dir: Path | None = None,
    features_root: Path = DATA_FEATURES_DIR,
    vectorizer_dir: Path = VECTORIZERS_DIR,
    tagged_dir: Path = CTRL_TAGGED_DIR,
    clean_dir: Path = OPENITI_CLEAN_DIR,
    quran_tagged: Path = QURAN_TAGGED_PATH,
    limit: int | None = None,
    skip_fig: bool = False,
    min_df: int | None = None,
    max_features: int | None = None,
    units: Sequence[str] | None = None,
    analyzer: Any | None = None,
    quran_tagger: Any | None = None,
    skip_root_if_unavailable: bool = True,
) -> dict[str, Any]:
    wanted = list(units) if units is not None else list(UNITS)
    frame_word = load_windows_frame(
        window_size=window_size, processed_dir=processed_dir, limit=limit
    )
    need_tags = any(u in {"lemma", "root"} for u in wanted)
    frame_tagged = (
        load_feature_index(window_size=window_size, processed_dir=processed_dir, limit=limit)
        if need_tags
        else frame_word
    )
    tokens_by_doc: dict[str, list[str]] = {}
    if need_tags and "tokens" in frame_tagged.columns:
        for rec in frame_tagged.itertuples(index=False):
            if str(rec.corpus) != "quran":
                continue
            raw = rec.tokens
            if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                raise ValueError(f"{rec.document_id}: okno Koranu bez tokens")
            tokens_by_doc[str(rec.document_id)] = [str(t) for t in list(raw)]

    live_analyzer = analyzer
    root_cache: dict[tuple[str, str], str] = {}
    if "root" in wanted and live_analyzer is None:
        live_analyzer = make_analyzer(config.tagger.database)
        if live_analyzer is None and skip_root_if_unavailable:
            wanted = [u for u in wanted if u != "root"]

    tagged_texts: dict[str, list[str]] = {}
    tag_fields = [u for u in wanted if u in {"lemma", "root"}]
    if tag_fields:
        ctrl_map = collect_ctrl_texts(
            frame_tagged,
            fields=tag_fields,
            tagged_dir=tagged_dir,
            clean_dir=clean_dir,
            window_size=window_size,
            min_tail_ratio=config.segmentation.min_tail_ratio,
            max_window_ratio=config.segmentation.max_window_ratio,
            analyzer=live_analyzer,
            root_cache=root_cache,
        )
        q_map = collect_quran_texts(
            frame_tagged,
            tokens_by_doc,
            fields=tag_fields,
            quran_tagged=quran_tagged,
            analyzer=live_analyzer,
            root_cache=root_cache,
            tagger=quran_tagger,
        )
        for field in tag_fields:
            merged: list[str] = []
            for i in range(len(frame_tagged)):
                if str(frame_tagged.iloc[i]["corpus"]) == "quran":
                    merged.append(q_map[field][i])
                else:
                    merged.append(ctrl_map[field][i])
            tagged_texts[field] = merged

    results: dict[str, Any] = {}
    main_payload: dict[str, Any] | None = None
    root_note = ""
    for unit in wanted:
        if unit == "word":
            texts = [str(t or "") for t in frame_word["text_norm_strict"].tolist()]
            idx_frame = frame_word
        elif unit in {"lemma", "root"}:
            texts = tagged_texts[unit]
            idx_frame = frame_tagged
            if unit == "root" and not any(texts):
                root_note = "root_pred puste we wszystkich oknach"
                if skip_root_if_unavailable:
                    continue
                raise ValueError(root_note)
        else:
            raise ValueError(f"Nieznana jednostka F3: {unit}")
        payload = extract_unit(
            idx_frame,
            texts,
            unit=unit,
            config=config,
            vectorizer_dir=vectorizer_dir,
            features_root=features_root,
            min_df=min_df,
            max_features=max_features,
        )
        results[unit] = {k: v for k, v in payload.items() if k not in {"matrix", "index", "feature_names"}}
        results[unit]["n_features_named"] = len(payload["feature_names"])
        if unit == MAIN_UNIT or main_payload is None:
            main_payload = payload

    if not results:
        raise ValueError("F3: zadna jednostka nie zostala policzona")
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
        "unit": main_payload["variant"],
    }
    figure_path = None
    if not skip_fig:
        from src.viz.fig42_lexical import save_fig_42

        saved = save_fig_42(fig_data, config_hash=config.config_hash())
        figure_path = rel_to_repo(saved.png)

    skipped_root = "root" not in results
    return {
        "task": "T-023",
        "family": FAMILY,
        "window_size": window_size,
        "config_hash": config.config_hash(),
        "variants": results,
        "n_windows": int(len(frame_word)),
        "n_ctrl_train": int((frame_word["split"].astype(str) == TRAIN_SPLIT).sum()),
        "n_ctrl_test": int((frame_word["split"].astype(str) == "ctrl_test").sum()),
        "n_quran": int((frame_word["corpus"].astype(str) == "quran").sum()),
        "figure": figure_path,
        "root_skipped": skipped_root,
        "root_cache_size": len(root_cache),
        "note": (
            "F3 TF-IDF word/lemma/root 1-2 gram, fit CTRL-TRAIN, annotation predicted. "
            "Status support (topic leakage). E-01=T-029. "
            + (root_note or ("root z CALIMA lookup (token, lemma_pred)." if "root" in results else "wariant root pominiety."))
        ),
        "_fig_data": fig_data,
    }


def write_lexical_report(
    payload: dict[str, Any],
    *,
    path: Path = LEXICAL_REPORT_PATH,
    config_hash: str | None = None,
) -> Path:
    out = {k: v for k, v in payload.items() if not str(k).startswith("_")}
    if config_hash:
        out["config_hash"] = config_hash
    write_json(path, out)
    return path
