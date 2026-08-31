"""T-022: F2 function words — czestosci wzgledne segmentow POS z whitelist.

Lista NIE jest reczna: K najczestszych form z CTRL-TRAIN (G4). Proklityki
sa osobnymi jednostkami (morph_pred / bw). Wersja bez segmentacji jest bledem.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from scipy import sparse

from src.annotate.tagger import parse_bw_with_pos
from src.annotate.tagset_map import load_camel_pos_map
from src.config import Config
from src.data.detect_quran_quotes import quran_ortho_words
from src.data.download_eqtb import INTERIM_TOKENS_PATH
from src.data.segment import cut_unit
from src.features.base import (
    TRAIN_SPLIT,
    assert_ctrl_train_only,
    fit_standard_scaler,
    n_zero_rows,
    nan_inf_count,
    norm_token_correlation,
    row_l2_norms,
)
from src.features.character import load_windows_frame, save_sparse_matrix
from src.paths import (
    CTRL_TAGGED_DIR,
    DATA_FEATURES_DIR,
    FUNCTION_REPORT_PATH,
    OPENITI_CLEAN_DIR,
    QURAN_TAGGED_PATH,
    VECTORIZERS_DIR,
    rel_to_repo,
    windows_dir,
)
from src.schemas import FeatureMatrix, GuardrailViolationError
from src.utils.io import ensure_dir, write_json

# configs/features/function.yaml — nie w Config, zeby nie ruszac config_hash T-021.
POS_WHITELIST: frozenset[str] = frozenset(
    {"PREP", "CONJ", "PART", "PRON", "DEM", "REL", "NEG", "INTG", "SUB"}
)
PROCLITIC_POS: dict[str, str] = {
    "و": "CONJ",
    "ف": "CONJ",
    "ب": "PREP",
    "ل": "PREP",
    "ك": "PREP",
    "س": "PART",
    "ال": "DET",
}
ENCLITIC_PRON: frozenset[str] = frozenset(
    {"ه", "ها", "هم", "هن", "هما", "ك", "كم", "كن", "كما", "ي", "ني", "نا"}
)
TOP_K_GRID: tuple[int, ...] = (100, 300, 1000)
MAIN_K = 1000
NORM_R_MAX = 0.3
MAIN_WINDOW_SIZE = 400
FAMILY = "function_words"


def pos_keys(pos: str) -> set[str]:
    raw = str(pos or "").strip()
    if not raw:
        return set()
    keys = {raw.upper()}
    rec = load_camel_pos_map().get(raw.lower())
    if rec is not None:
        if rec.coarse:
            keys.add(rec.coarse)
        if rec.eqtb_pos:
            keys.add(rec.eqtb_pos.upper())
    return {k for k in keys if k}


def is_function_pos(pos: str, whitelist: frozenset[str] = POS_WHITELIST) -> bool:
    return bool(pos_keys(pos) & whitelist)


def expand_morph_pred(morph: str, stem_pos: str) -> list[tuple[str, str]]:
    """Rozbij ``morph_pred`` (formy z ``+``) na (forma, POS). Proklityki z configu."""
    parts = [p for p in str(morph or "").split("+") if p]
    if not parts:
        return []
    if len(parts) == 1:
        return [(parts[0], stem_pos)]
    i = 0
    j = len(parts)
    left: list[tuple[str, str]] = []
    while i < j - 1 and parts[i] in PROCLITIC_POS:
        left.append((parts[i], PROCLITIC_POS[parts[i]]))
        i += 1
    right: list[tuple[str, str]] = []
    while j - 1 > i and parts[j - 1] in ENCLITIC_PRON:
        right.append((parts[j - 1], "PRON"))
        j -= 1
    right.reverse()
    stem_parts = parts[i:j]
    out = list(left)
    if stem_parts:
        out.append(("".join(stem_parts), stem_pos))
    out.extend(right)
    return out if out else [(str(morph), stem_pos)]


def expand_tagged_word(
    *,
    token: str,
    pos_pred: str,
    pos_raw: str = "",
    morph_pred: str = "",
    bw_pred: str = "",
) -> list[tuple[str, str]]:
    """Jednostki F2 = segmenty morfologiczne. Brak morph/bw przy niepustym tokenie = blad."""
    token = str(token or "")
    morph = str(morph_pred or "")
    bw = str(bw_pred or "")
    stem_pos = str(pos_raw or pos_pred or "")
    if bw and bw not in {"_", "NOAN"}:
        segs = parse_bw_with_pos(bw)
        if segs:
            return segs
    if morph:
        segs = expand_morph_pred(morph, stem_pos or str(pos_pred or ""))
        if segs:
            return segs
    if token:
        raise GuardrailViolationError(
            "T-022: F2 wymaga segmentacji morfologicznej (morph_pred/bw). "
            "Nie wolno podstawic tokenu ortograficznego."
        )
    return []


def assert_segmentation(rows: Sequence[Mapping[str, Any]]) -> None:
    n_plus = 0
    n_bw = 0
    n_empty = 0
    for row in rows:
        morph = str(row.get("morph_pred") or "")
        bw = str(row.get("bw_pred") or "")
        token = str(row.get("token") or "")
        if "+" in morph or ("/" in bw and "+" in bw):
            n_plus += 1
        if bw and "/" in bw:
            n_bw += 1
        if token and not morph and not bw:
            n_empty += 1
    if n_empty:
        raise GuardrailViolationError(
            f"T-022: {n_empty} tokenow bez morph_pred/bw — F2 bez segmentacji jest bezuzyteczna."
        )
    if n_plus == 0 and n_bw == 0:
        raise GuardrailViolationError(
            "T-022: brak wielosegmentowych analiz. Nie podstawiam tokenizacji bialej."
        )


def keep_indices_after_deletions(source: Sequence[str], kept: Sequence[str]) -> list[int]:
    """Indeksy ``source`` odpowiadajace ``kept`` (T-016 usuwa cytaty, nie przestawia)."""
    i = 0
    out: list[int] = []
    n = len(source)
    for tok in kept:
        while i < n and source[i] != tok:
            i += 1
        if i >= n:
            raise ValueError("align capped→clean: keep nie jest podciagiem tagged")
        out.append(i)
        i += 1
    return out


def function_forms_from_rows(
    frame: pd.DataFrame,
    *,
    whitelist: frozenset[str] = POS_WHITELIST,
) -> tuple[list[str], int]:
    """Zwraca (formy function-word, n_segments) dla wierszy tagow jednego okna."""
    has_bw = "bw_pred" in frame.columns
    forms: list[str] = []
    n_seg = 0
    for rec in frame.itertuples(index=False):
        bw = str(getattr(rec, "bw_pred", "") or "") if has_bw else ""
        segs = expand_tagged_word(
            token=str(rec.token),
            pos_pred=str(rec.pos_pred),
            pos_raw=str(getattr(rec, "pos_raw_pred", "") or ""),
            morph_pred=str(rec.morph_pred),
            bw_pred=bw,
        )
        n_seg += len(segs)
        for form, pos in segs:
            if is_function_pos(pos, whitelist):
                forms.append(form)
    return forms, n_seg


def fit_top_k_vocab(
    train_forms: Sequence[Sequence[str]],
    splits: Sequence[str],
    k: int,
) -> list[str]:
    assert_ctrl_train_only(splits)
    counts: Counter[str] = Counter()
    for forms in train_forms:
        counts.update(forms)
    if not counts:
        raise ValueError("CTRL-TRAIN nie ma zadnych function words po filtrze POS")
    return [w for w, _n in counts.most_common(int(k))]


def relative_freq_matrix(
    window_forms: Sequence[Sequence[str]],
    n_segments: Sequence[int],
    vocab: Sequence[str],
) -> sparse.csr_matrix:
    vocab_index = {w: i for i, w in enumerate(vocab)}
    n_rows = len(window_forms)
    n_cols = len(vocab)
    data: list[float] = []
    indices: list[int] = []
    indptr = [0]
    for forms, n_seg in zip(window_forms, n_segments, strict=True):
        local: Counter[str] = Counter(forms)
        denom = float(n_seg) if n_seg else 0.0
        for form, count in local.items():
            col = vocab_index.get(form)
            if col is None or denom <= 0.0:
                continue
            data.append(count / denom)
            indices.append(col)
        indptr.append(len(data))
    return sparse.csr_matrix(
        (np.asarray(data, dtype=np.float64), indices, indptr),
        shape=(n_rows, n_cols),
    )


def _family_dir(config_hash: str, variant: str, *, root: Path = DATA_FEATURES_DIR) -> Path:
    return root / FAMILY / config_hash / variant


def persist_fw_vocab(
    vocab: Sequence[str],
    *,
    k: int,
    config_hash: str,
    out_dir: Path = VECTORIZERS_DIR,
) -> Path:
    ensure_dir(out_dir)
    path = out_dir / f"{FAMILY}_k{int(k)}_{config_hash}.joblib"
    joblib.dump(
        {
            "vocabulary": list(vocab),
            "k": int(k),
            "pos_whitelist": sorted(POS_WHITELIST),
            "family": FAMILY,
        },
        path,
    )
    return path


def align_ctrl_book_tags(
    *,
    version_id: str,
    tagged_dir: Path,
    clean_dir: Path,
) -> pd.DataFrame:
    tagged_path = tagged_dir / f"{version_id}.parquet"
    if not tagged_path.is_file():
        raise FileNotFoundError(f"Brak tagow CTRL {tagged_path} (T-015/H1)")
    clean_path = clean_dir / version_id
    if not clean_path.is_file():
        raise FileNotFoundError(f"Brak openiti_clean {clean_path} (T-016)")
    tagged = pd.read_parquet(tagged_path)
    needed = {"token", "pos_pred", "morph_pred"}
    missing = needed - set(tagged.columns)
    if missing:
        raise ValueError(f"{tagged_path.name}: brak kolumn {sorted(missing)}")
    capped_tokens = [str(t) for t in tagged["token"].tolist()]
    clean_tokens = clean_path.read_text(encoding="utf-8").split()
    keep = keep_indices_after_deletions(capped_tokens, clean_tokens)
    aligned = tagged.iloc[keep].reset_index(drop=True)
    if [str(t) for t in aligned["token"].tolist()] != clean_tokens:
        raise AssertionError(f"{version_id}: tagged po align != openiti_clean")
    return aligned


def collect_ctrl_windows(
    index: pd.DataFrame,
    *,
    tagged_dir: Path,
    clean_dir: Path,
    window_size: int,
    min_tail_ratio: float,
    max_window_ratio: float,
) -> tuple[list[list[str]], list[int], int]:
    """Formy F2 i n_segments w kolejnosci ``index`` (tylko wiersze CTRL)."""
    ctrl = index.loc[index["corpus"].astype(str) == "ctrl"].copy()
    by_doc = {str(d): i for i, d in enumerate(index["document_id"].astype(str))}
    forms_out: list[list[str] | None] = [None] * len(index)
    nseg_out: list[int | None] = [None] * len(index)
    n_multi = 0
    sample_rows: list[dict[str, Any]] = []
    versions = sorted(
        {
            str(v)
            for v in ctrl["version_id"].astype(str).tolist()
            if str(v) and str(v) not in {"nan", "None", ""}
        }
    )
    for vi, version_id in enumerate(versions):
        aligned = align_ctrl_book_tags(
            version_id=version_id, tagged_dir=tagged_dir, clean_dir=clean_dir
        )
        if vi == 0:
            sample_rows = aligned.head(64).to_dict("records")
        n_multi += int(aligned["morph_pred"].fillna("").astype(str).str.contains(r"\+").sum())
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
                raise AssertionError(
                    f"{doc}: tagged span {len(chunk)} != n_tokens {expected_n}"
                )
            forms, n_seg = function_forms_from_rows(chunk)
            forms_out[row_i] = forms
            nseg_out[row_i] = n_seg
        if (vi + 1) % 50 == 0 or vi + 1 == len(versions):
            print(f"F2 ctrl books {vi + 1}/{len(versions)}", flush=True)
    if sample_rows:
        assert_segmentation(sample_rows)
    if n_multi == 0:
        raise GuardrailViolationError("T-022: CTRL tagged bez segmentacji (brak '+').")
    missing = [
        str(index.iloc[i]["document_id"])
        for i, val in enumerate(forms_out)
        if val is None and str(index.iloc[i]["corpus"]) == "ctrl"
    ]
    if missing:
        raise FileNotFoundError(f"Brak tagow dla okien CTRL: {missing[:5]} (+{len(missing)})")
    return (
        [f or [] for f in forms_out],
        [n or 0 for n in nseg_out],
        n_multi,
    )


def tag_quran_predicted(
    *,
    eqtb_path: Path = INTERIM_TOKENS_PATH,
    out_path: Path = QURAN_TAGGED_PATH,
    tagger: Any | None = None,
) -> Path:
    """Tagi CAMeL MLE na slowach ortograficznych EQTB (G1: *_pred, nie gold)."""
    if out_path.is_file():
        existing = pd.read_parquet(out_path)
        if len(existing) > 0 and "morph_pred" in existing.columns:
            return out_path
    if not eqtb_path.is_file():
        raise FileNotFoundError(f"Brak {eqtb_path} — T-009")
    if tagger is None:
        from src.annotate.tagger import CamelMLETagger

        tagger = CamelMLETagger()
    eqtb = pd.read_parquet(eqtb_path)
    words = quran_ortho_words(eqtb)
    rows: list[dict[str, str | int]] = []
    current_key: tuple[int, int] | None = None
    bucket: list[Any] = []

    def flush() -> None:
        if not bucket:
            return
        tokens = [w.token for w in bucket]
        predicted = tagger.tag_sentence(tokens)
        if len(predicted) != len(bucket):
            raise AssertionError("tagger zwrocil inna liczbe slow niz ajaty")
        for word, pred in zip(bucket, predicted, strict=True):
            rows.append(
                {
                    "surah_id": int(word.surah_id),
                    "verse_id": int(word.verse_id),
                    "word_id": int(word.word_id),
                    "token": word.token,
                    "pos_pred": pred.pos_coarse,
                    "pos_raw_pred": pred.pos_raw,
                    "lemma_pred": pred.lemma_norm,
                    "morph_pred": "+".join(pred.segments_norm),
                    "bw_pred": "",
                }
            )

    for word in words:
        key = (word.surah_id, word.verse_id)
        if current_key is not None and key != current_key:
            flush()
            bucket = []
        current_key = key
        bucket.append(word)
    flush()
    ensure_dir(out_path.parent)
    pd.DataFrame(rows).to_parquet(out_path, index=False)
    return out_path


def find_token_span(
    haystack: Sequence[str], needle: Sequence[str], *, start: int = 0
) -> tuple[int, int]:
    needle_l = [str(x) for x in needle]
    hay = [str(x) for x in haystack]
    m = len(needle_l)
    if m == 0:
        raise ValueError("puste okno Koranu")
    n = len(hay)
    first = needle_l[0]
    ranges = [range(start, n - m + 1)]
    if start > 0:
        ranges.append(range(0, start))
    for rng in ranges:
        for i in rng:
            if hay[i] == first and hay[i : i + m] == needle_l:
                return i, i + m
    raise ValueError("okno Koranu nie znajduje sie w strumieniu tagged")


def collect_quran_windows(
    index: pd.DataFrame,
    tokens_by_doc: Mapping[str, Sequence[str]],
    *,
    quran_tagged: Path,
    tagger: Any | None = None,
) -> tuple[list[list[str]], list[int]]:
    qmask = index["corpus"].astype(str) == "quran"
    if not bool(qmask.any()):
        return [[] for _ in range(len(index))], [0] * len(index)
    path = tag_quran_predicted(out_path=quran_tagged, tagger=tagger)
    tagged = pd.read_parquet(path)
    assert_segmentation(tagged.head(128).to_dict("records"))
    stream_tokens = [str(t) for t in tagged["token"].tolist()]
    forms_out: list[list[str]] = [[] for _ in range(len(index))]
    nseg_out = [0] * len(index)
    cursor = 0
    for pos in range(len(index)):
        if str(index.iloc[pos]["corpus"]) != "quran":
            continue
        doc = str(index.iloc[pos]["document_id"])
        needle = list(tokens_by_doc[doc])
        lo, hi = find_token_span(stream_tokens, needle, start=cursor)
        cursor = hi
        chunk = tagged.iloc[lo:hi]
        forms, n_seg = function_forms_from_rows(chunk)
        forms_out[pos] = forms
        nseg_out[pos] = n_seg
    return forms_out, nseg_out


def load_feature_index(
    *,
    window_size: int = MAIN_WINDOW_SIZE,
    processed_dir: Path | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    frame = load_windows_frame(
        window_size=window_size, processed_dir=processed_dir, limit=None
    )
    folder = (
        Path(processed_dir) / f"windows_{window_size}"
        if processed_dir is not None
        else windows_dir(window_size)
    )
    ctrl_path = folder / "ctrl.parquet"
    quran_path = folder / "quran.parquet"
    if ctrl_path.is_file():
        extra_ctrl = pd.read_parquet(ctrl_path, columns=["document_id", "version_id"])
        frame = frame.merge(extra_ctrl, on="document_id", how="left")
    if quran_path.is_file():
        extra_q = pd.read_parquet(quran_path, columns=["document_id", "tokens"])
        frame = frame.merge(extra_q, on="document_id", how="left")
    if limit is not None:
        frame = frame.iloc[: int(limit)].copy()
    return frame.reset_index(drop=True)


def extract_k(
    *,
    index: pd.DataFrame,
    window_forms: Sequence[Sequence[str]],
    n_segments: Sequence[int],
    k: int,
    config: Config,
    vectorizer_dir: Path,
    features_root: Path,
) -> dict[str, Any]:
    train_mask = index["split"].astype(str) == TRAIN_SPLIT
    train_idx = np.flatnonzero(train_mask.to_numpy())
    if train_idx.size == 0:
        raise ValueError("Brak okien ctrl_train — uruchom T-020")
    train_forms = [window_forms[i] for i in train_idx]
    train_splits = index.iloc[train_idx]["split"].astype(str).tolist()
    vocab = fit_top_k_vocab(train_forms, train_splits, k)
    matrix = relative_freq_matrix(window_forms, n_segments, vocab)
    norms = row_l2_norms(matrix)
    corr = norm_token_correlation(norms, index["n_tokens"].tolist())
    if abs(float(corr["r"])) >= NORM_R_MAX:
        csr = sparse.csr_matrix(matrix, dtype=np.float64)
        row_norm = np.sqrt(np.asarray(csr.multiply(csr).sum(axis=1)).ravel())
        row_norm[row_norm == 0.0] = 1.0
        matrix = sparse.diags(1.0 / row_norm) @ csr
        norms = row_l2_norms(matrix)
        corr = norm_token_correlation(norms, index["n_tokens"].tolist())
        corr["note"] = (corr.get("note") or "") + " L2 po f_w (r surowe >= 0.3)"
    n_nan = nan_inf_count(matrix)
    n_zero = n_zero_rows(matrix)
    if n_nan:
        raise AssertionError(f"NaN/inf w macierzy F2: {n_nan}")
    if n_zero:
        raise AssertionError(f"zerowe wektory F2 k={k}: {n_zero}")
    train_mat = matrix[train_mask.to_numpy()]
    scaler = fit_standard_scaler(train_mat, train_splits, with_mean=False)
    variant = f"k{int(k)}"
    FeatureMatrix(
        family=FAMILY,
        config_label="FUNCTIONAL",
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
        distance_main="burrows_delta",
    )
    vec_path = persist_fw_vocab(
        vocab, k=k, config_hash=config.config_hash(), out_dir=vectorizer_dir
    )
    scaler_path = vectorizer_dir / f"{FAMILY}_{variant}_scaler_{config.config_hash()}.joblib"
    ensure_dir(vectorizer_dir)
    joblib.dump(scaler, scaler_path)
    out_dir = save_sparse_matrix(
        matrix,
        index[["document_id", "corpus", "split", "n_tokens"]].assign(variant=variant),
        directory=_family_dir(config.config_hash(), variant, root=features_root),
        feature_names=vocab,
        extra_meta={
            "family": FAMILY,
            "variant": variant,
            "k": int(k),
            "config_hash": config.config_hash(),
            "fitted_on": TRAIN_SPLIT,
            "value": "relative_frequency",
            "pos_whitelist": sorted(POS_WHITELIST),
            "vectorizer": rel_to_repo(vec_path),
            "scaler": rel_to_repo(scaler_path),
            "n_train": int(train_mask.sum()),
            "norm_token_r": corr["r"],
            "norm_token_note": corr.get("note") or "",
        },
    )
    return {
        "variant": variant,
        "k": int(k),
        "n_rows": int(matrix.shape[0]),
        "n_cols": int(matrix.shape[1]),
        "nnz": int(sparse.csr_matrix(matrix).nnz),
        "n_train": int(train_mask.sum()),
        "n_zero_rows": n_zero,
        "n_nan_inf": n_nan,
        "norm_token": corr,
        "vectorizer": rel_to_repo(vec_path),
        "dir": rel_to_repo(out_dir),
        "feature_names": vocab,
        "matrix": matrix,
        "index": index,
    }


def run_function_word_features(
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
    k_grid: Sequence[int] | None = None,
    quran_tagger: Any | None = None,
) -> dict[str, Any]:
    frame = load_feature_index(
        window_size=window_size, processed_dir=processed_dir, limit=limit
    )
    if "version_id" not in frame.columns:
        raise ValueError("okna bez version_id — T-019")
    tokens_by_doc: dict[str, list[str]] = {}
    if "tokens" in frame.columns:
        for rec in frame.itertuples(index=False):
            if str(rec.corpus) != "quran":
                continue
            raw = rec.tokens
            if raw is None or (isinstance(raw, float) and pd.isna(raw)):
                raise ValueError(f"{rec.document_id}: okno Koranu bez tokens")
            tokens_by_doc[str(rec.document_id)] = [str(t) for t in list(raw)]
    ctrl_forms, ctrl_nseg, n_multi = collect_ctrl_windows(
        frame,
        tagged_dir=tagged_dir,
        clean_dir=clean_dir,
        window_size=window_size,
        min_tail_ratio=config.segmentation.min_tail_ratio,
        max_window_ratio=config.segmentation.max_window_ratio,
    )
    q_forms, q_nseg = collect_quran_windows(
        frame,
        tokens_by_doc,
        quran_tagged=quran_tagged,
        tagger=quran_tagger,
    )
    window_forms: list[list[str]] = []
    n_segments: list[int] = []
    for i in range(len(frame)):
        if str(frame.iloc[i]["corpus"]) == "quran":
            window_forms.append(q_forms[i])
            n_segments.append(q_nseg[i])
        else:
            window_forms.append(ctrl_forms[i])
            n_segments.append(ctrl_nseg[i])

    grid = list(k_grid) if k_grid is not None else list(TOP_K_GRID)
    results: dict[str, Any] = {}
    main_payload: dict[str, Any] | None = None
    for k in grid:
        payload = extract_k(
            index=frame,
            window_forms=window_forms,
            n_segments=n_segments,
            k=int(k),
            config=config,
            vectorizer_dir=vectorizer_dir,
            features_root=features_root,
        )
        results[payload["variant"]] = {
            key: val
            for key, val in payload.items()
            if key not in {"matrix", "index", "feature_names"}
        }
        results[payload["variant"]]["n_features_named"] = len(payload["feature_names"])
        if int(k) == MAIN_K or (MAIN_K not in grid and main_payload is None):
            main_payload = payload

    assert main_payload is not None
    matrix = main_payload["matrix"]
    index = main_payload["index"]
    names = main_payload["feature_names"]
    train_m = (index["split"].astype(str) == TRAIN_SPLIT).to_numpy()
    test_m = (index["split"].astype(str) == "ctrl_test").to_numpy()
    quran_m = (index["corpus"].astype(str) == "quran").to_numpy()
    from src.features.character import mean_by_mask

    fig_data = {
        "feature_names": names,
        "mean_ctrl_train": mean_by_mask(matrix, train_m).tolist(),
        "mean_ctrl_test": mean_by_mask(matrix, test_m).tolist(),
        "mean_quran": mean_by_mask(matrix, quran_m).tolist(),
        "k": int(main_payload["k"]),
    }
    figure_path = None
    if not skip_fig:
        from src.viz.fig41_function import save_fig_41

        saved = save_fig_41(fig_data, config_hash=config.config_hash())
        figure_path = rel_to_repo(saved.png)

    return {
        "task": "T-022",
        "family": FAMILY,
        "window_size": window_size,
        "config_hash": config.config_hash(),
        "variants": results,
        "n_windows": int(len(frame)),
        "n_ctrl_train": int((frame["split"].astype(str) == TRAIN_SPLIT).sum()),
        "n_ctrl_test": int((frame["split"].astype(str) == "ctrl_test").sum()),
        "n_quran": int((frame["corpus"].astype(str) == "quran").sum()),
        "n_multi_segment_ctrl": int(n_multi),
        "figure": figure_path,
        "note": (
            "F2: czestosc wzgledna segmentow POS whitelist, vocab z CTRL-TRAIN. "
            "Proklityki z morph_pred. Koran: CAMeL MLE *_pred (nie gold). E-01=T-029."
        ),
        "_fig_data": fig_data,
    }


def write_function_report(
    payload: dict[str, Any],
    *,
    path: Path = FUNCTION_REPORT_PATH,
    config_hash: str | None = None,
) -> Path:
    out = {k: v for k, v in payload.items() if not str(k).startswith("_")}
    if config_hash:
        out["config_hash"] = config_hash
    write_json(path, out)
    return path
