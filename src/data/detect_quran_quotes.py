"""T-016: cytaty Koranu w CTRL (docs/03_DATA.md §7a, 09_DECISIONS.md §6).

Nie liczy stylometrii Koranu — indeks 7-gramow z EQTB (imlaai, strict) sluzy
tylko do czyszczenia OpenITI. Wejscie: ``ctrl_capped/``. Wyjscie: ``openiti_clean/``.

Oprocz exact tuple match: zlaczone 7 slow Koranu vs zmienna liczba tokenow CTRL
(``concat_key``, ``اا→ا``). Lapie rozjazd word_id EQTB (يايها) vs whitespace
OpenITI (يا ايها) przy tym samym ciagu Q33:56.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from src.config import QuotesCfg
from src.data.normalize_arabic import normalize
from src.paths import (
    CTRL_CAPPED_DIR,
    DATA_INTERIM_DIR,
    GENRES_PATH,
    OPENITI_CLEAN_DIR,
    QUOTE_AUDIT_PATH,
    QUOTE_REPORT_PATH,
)
from src.utils.io import ensure_dir, read_json, write_json
from src.utils.seed import new_rng

EQTB_TOKENS_PATH: Path = DATA_INTERIM_DIR / "eqtb_tokens.parquet"


@dataclass(frozen=True)
class OrthoWord:
    """Slowo ortograficzne Koranu (chapter, verse, word) po normalize(profile)."""

    surah_id: int
    verse_id: int
    word_id: int
    token: str


class FuzzyIndex(Protocol):
    def add(self, gram: tuple[str, ...]) -> None: ...

    def query(self, gram: tuple[str, ...]) -> bool: ...


def token_ngrams(tokens: Sequence[str], n: int) -> list[tuple[str, ...]]:
    if n <= 0:
        raise ValueError(f"n musi byc >= 1, dostano {n}")
    if len(tokens) < n:
        return []
    return [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def concat_key(parts: Sequence[str]) -> str:
    """Złacz tokeny i zloż podwójne alify powstające na granicy (يا+ايها → يايها).

    EQTB skleja wołacz ي+أيها w jedno ``word_id`` (يايها); OpenITI ma spację
    i alif (يا ايها). Po złączeniu i ``اا→ا`` 7 słów Koranu pokrywa 8 tokenów CTRL.
    """
    return "".join(parts).replace("اا", "ا")


def token_concat_needles(tokens: Sequence[str], n: int) -> set[str]:
    if n <= 0 or len(tokens) < n:
        return set()
    return {concat_key(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def merge_intervals(intervals: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    ordered = sorted((int(lo), int(hi)) for lo, hi in intervals if hi > lo)
    if not ordered:
        return []
    merged = [ordered[0]]
    for lo, hi in ordered[1:]:
        prev_lo, prev_hi = merged[-1]
        if lo <= prev_hi:
            merged[-1] = (prev_lo, max(prev_hi, hi))
        else:
            merged.append((lo, hi))
    return merged


def pad_spans(
    spans: Sequence[tuple[int, int]],
    *,
    margin: int,
    length: int,
) -> list[tuple[int, int]]:
    expanded: list[tuple[int, int]] = []
    for lo, hi in spans:
        a = max(0, int(lo) - margin)
        b = min(length, int(hi) + margin)
        if b > a:
            expanded.append((a, b))
    return merge_intervals(expanded)


def merge_hit_spans(
    hit_starts: Iterable[int],
    *,
    n: int,
    margin: int,
    length: int,
) -> list[tuple[int, int]]:
    """Kazde trafienie na pozycji i pokrywa [i-margin, i+n+margin) (exclusive hi)."""
    return pad_spans(((int(s), int(s) + n) for s in hit_starts), margin=margin, length=length)


def concat_prefix_index(needles: set[str], *, max_pref: int = 12) -> set[str]:
    prefixes: set[str] = set()
    for needle in needles:
        limit = min(max_pref, len(needle))
        for length_pref in range(1, limit + 1):
            prefixes.add(needle[:length_pref])
    return prefixes


def find_concat_hits(
    tokens: Sequence[str],
    needles: set[str],
    *,
    n: int,
    extra: int = 6,
    prefixes: set[str] | None = None,
    skip: set[int] | None = None,
) -> list[tuple[int, int]]:
    """Trafienia o zmiennej liczbie tokenów CTRL, których złączenie = 7 słów Koranu."""
    if not needles or n <= 0:
        return []
    max_len = max(len(s) for s in needles)
    pref = prefixes if prefixes is not None else concat_prefix_index(needles)
    skip_at = skip or set()
    max_tokens = n + extra
    hits: list[tuple[int, int]] = []
    length = len(tokens)
    for i in range(length):
        if i in skip_at:
            continue
        first = concat_key((tokens[i],))
        if first not in pref and first[:12] not in pref:
            continue
        acc = ""
        hi = min(length, i + max_tokens)
        for j in range(i, hi):
            acc = concat_key((acc, tokens[j]))
            if len(acc) > max_len:
                break
            if acc in needles:
                hits.append((i, j + 1))
                break
    return hits


def apply_spans(tokens: Sequence[str], spans: Sequence[tuple[int, int]]) -> tuple[list[str], int]:
    drop = [False] * len(tokens)
    for lo, hi in spans:
        for i in range(lo, hi):
            drop[i] = True
    kept = [tok for tok, gone in zip(tokens, drop, strict=True) if not gone]
    return kept, sum(drop)


def quran_ortho_words(eqtb: pd.DataFrame, *, profile: str = "strict") -> list[OrthoWord]:
    """Slowa ortograficzne w kolejnosci mushaf (chapter, verse, word), normalize(profile)."""
    needed = {"chapter_id", "verse_id", "word_id", "imlaai_token"}
    missing = needed - set(eqtb.columns)
    if missing:
        raise ValueError(f"EQTB bez kolumn {sorted(missing)}")
    real = eqtb.loc[eqtb["word_id"].astype(str).str.strip() != "0"].copy()
    real["_ch"] = real["chapter_id"].astype(int)
    real["_vs"] = real["verse_id"].astype(int)
    real["_wd"] = real["word_id"].astype(int)
    if "tok_id" in real.columns:
        real["_tok"] = pd.to_numeric(real["tok_id"], errors="coerce").fillna(0)
        real = real.sort_values(["_ch", "_vs", "_wd", "_tok"], kind="mergesort")
    else:
        real = real.sort_values(["_ch", "_vs", "_wd"], kind="mergesort")
    words: list[OrthoWord] = []
    for _, group in real.groupby(["_ch", "_vs", "_wd"], sort=False):
        surface = "".join(str(x) for x in group["imlaai_token"].tolist())
        norm = normalize(surface, profile)  # type: ignore[arg-type]
        if not norm:
            continue
        words.append(
            OrthoWord(
                surah_id=int(group["_ch"].iloc[0]),
                verse_id=int(group["_vs"].iloc[0]),
                word_id=int(group["_wd"].iloc[0]),
                token=norm,
            )
        )
    return words


def quran_word_tokens(eqtb: pd.DataFrame, *, profile: str = "strict") -> list[str]:
    """Slowa ortograficzne w kolejnosci mushaf (chapter, verse, word), normalize(strict)."""
    return [word.token for word in quran_ortho_words(eqtb, profile=profile)]


class JaccardFuzzy:
    """Dokladny Jaccard na zbiorze tokenow — tylko testy (O(n) na query)."""

    def __init__(self, *, threshold: float) -> None:
        self.threshold = threshold
        self._grams: list[frozenset[str]] = []

    def add(self, gram: tuple[str, ...]) -> None:
        self._grams.append(frozenset(gram))

    def query(self, gram: tuple[str, ...]) -> bool:
        query_set = frozenset(gram)
        if not query_set:
            return False
        for other in self._grams:
            union = query_set | other
            if not union:
                continue
            if len(query_set & other) / len(union) >= self.threshold:
                return True
        return False


class DatasketchFuzzy:
    def __init__(self, *, threshold: float, num_perm: int) -> None:
        from datasketch import MinHash, MinHashLSH

        self._MinHash = MinHash
        self.num_perm = num_perm
        self._lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
        self._n = 0

    def _minhash(self, gram: tuple[str, ...]) -> Any:
        mh = self._MinHash(num_perm=self.num_perm)
        for tok in gram:
            mh.update(tok.encode("utf-8"))
        return mh

    def add(self, gram: tuple[str, ...]) -> None:
        key = str(self._n)
        self._lsh.insert(key, self._minhash(gram))
        self._n += 1

    def query(self, gram: tuple[str, ...]) -> bool:
        return bool(self._lsh.query(self._minhash(gram)))


def make_fuzzy_index(cfg: QuotesCfg, *, use_datasketch: bool = True) -> FuzzyIndex:
    if use_datasketch:
        try:
            return DatasketchFuzzy(
                threshold=cfg.minhash_threshold, num_perm=cfg.minhash_num_perm
            )
        except ImportError as exc:
            raise ImportError(
                "T-016 wymaga datasketch (09_DECISIONS.md §1). "
                "pip install 'datasketch==2.0.0'"
            ) from exc
    return JaccardFuzzy(threshold=cfg.minhash_threshold)


def _prefilter_fuzzy(gram: tuple[str, ...], vocab: set[str], *, min_overlap: int = 5) -> bool:
    return sum(1 for tok in gram if tok in vocab) >= min_overlap


def scan_book(
    tokens: Sequence[str],
    *,
    exact: set[tuple[str, ...]],
    fuzzy: FuzzyIndex | None,
    vocab: set[str],
    cfg: QuotesCfg,
    concat_needles: set[str] | None = None,
    concat_prefixes: set[str] | None = None,
) -> dict[str, Any]:
    n = cfg.quote_ngram_n
    grams = token_ngrams(tokens, n)
    exact_hits: list[int] = []
    fuzzy_hits: list[int] = []
    raw_spans: list[tuple[int, int]] = []
    for i, gram in enumerate(grams):
        if gram in exact:
            exact_hits.append(i)
            raw_spans.append((i, i + n))
            continue
        if fuzzy is not None and _prefilter_fuzzy(gram, vocab) and fuzzy.query(gram):
            fuzzy_hits.append(i)
            raw_spans.append((i, i + n))
    concat_hits: list[int] = []
    if concat_needles:
        covered = {s for lo, hi in raw_spans for s in range(lo, hi)}
        for lo, hi in find_concat_hits(
            tokens,
            concat_needles,
            n=n,
            prefixes=concat_prefixes,
            skip=covered,
        ):
            if lo in covered:
                continue
            concat_hits.append(lo)
            raw_spans.append((lo, hi))
            covered.update(range(lo, hi))
    detected_spans = pad_spans(raw_spans, margin=0, length=len(tokens))
    spans = pad_spans(raw_spans, margin=cfg.match_margin_tokens, length=len(tokens))
    cleaned, n_removed = apply_spans(tokens, spans)
    n_detected = sum(hi - lo for lo, hi in detected_spans)
    return {
        "tokens_raw": len(tokens),
        "tokens_clean": len(cleaned),
        "tokens_removed": n_removed,
        "tokens_detected_spans": n_detected,
        "n_exact_hits": len(exact_hits),
        "n_fuzzy_hits": len(fuzzy_hits),
        "n_concat_hits": len(concat_hits),
        "cleaned": cleaned,
        "exact_hits": exact_hits,
        "fuzzy_hits": fuzzy_hits,
        "concat_hits": concat_hits,
        "spans": spans,
    }


def shuffle_exact_index(
    quran_tokens: Sequence[str], n: int, rng: Any
) -> set[tuple[str, ...]]:
    shuffled = [quran_tokens[i] for i in rng.permutation(len(quran_tokens))]
    return set(token_ngrams(shuffled, n))


def load_genre_map(path: Path = GENRES_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    frame = pd.read_csv(path)
    if "version_uri" not in frame.columns or "genre" not in frame.columns:
        return {}
    return {
        str(row["version_uri"]): str(row["genre"])
        for row in frame[["version_uri", "genre"]].to_dict("records")
    }


def _reservoir(
    rng: Any, k: int
) -> tuple[list[dict[str, Any]], Callable[[dict[str, Any]], None]]:
    buf: list[dict[str, Any]] = []
    n_seen = {"c": 0}

    def add(item: dict[str, Any]) -> None:
        n_seen["c"] += 1
        if len(buf) < k:
            buf.append(item)
            return
        j = int(rng.integers(0, n_seen["c"]))
        if j < k:
            buf[j] = item

    return buf, add


def clean_ctrl_quotes(
    *,
    quran_tokens: Sequence[str],
    input_dir: Path = CTRL_CAPPED_DIR,
    output_dir: Path = OPENITI_CLEAN_DIR,
    cfg: QuotesCfg,
    seed: int = 20260830,
    genre_map: dict[str, str] | None = None,
    fuzzy: FuzzyIndex | None = None,
    limit_books: int | None = None,
    audit_k: int = 100,
) -> dict[str, Any]:
    n = cfg.quote_ngram_n
    exact = set(token_ngrams(quran_tokens, n))
    concat_needles = token_concat_needles(quran_tokens, n)
    concat_prefixes = concat_prefix_index(concat_needles)
    vocab = {tok for gram in exact for tok in gram}
    if fuzzy is not None:
        for gram in exact:
            fuzzy.add(gram)
    rng_audit = new_rng(seed, "t016_audit")
    rng_shuffle = new_rng(seed, "t016_shuffle")
    matches, add_match = _reservoir(rng_audit, audit_k)
    nonmatches, add_non = _reservoir(rng_audit, audit_k)

    shuffle_index = shuffle_exact_index(quran_tokens, n, rng_shuffle)
    genres = genre_map if genre_map is not None else load_genre_map()
    ensure_dir(output_dir)
    books = sorted(p for p in input_dir.iterdir() if p.is_file() and p.name != "manifest.csv")
    if limit_books is not None:
        books = books[: int(limit_books)]

    per_book: list[dict[str, Any]] = []
    by_genre: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "tokens_raw": 0,
            "tokens_removed": 0,
            "tokens_detected_spans": 0,
            "tokens_shuffle_removed": 0,
            "n_books": 0,
        }
    )

    for path in books:
        tokens = path.read_text(encoding="utf-8").split()
        result = scan_book(
            tokens,
            exact=exact,
            fuzzy=fuzzy,
            vocab=vocab,
            cfg=cfg,
            concat_needles=concat_needles,
            concat_prefixes=concat_prefixes,
        )
        shuffle_hits = [
            i for i, gram in enumerate(token_ngrams(tokens, n)) if gram in shuffle_index
        ]
        shuffle_spans = merge_hit_spans(
            shuffle_hits, n=n, margin=cfg.match_margin_tokens, length=len(tokens)
        )
        _, shuffle_removed = apply_spans(tokens, shuffle_spans)
        cleaned: list[str] = result["cleaned"]
        text = " ".join(cleaned) + ("\n" if cleaned else "")
        (output_dir / path.name).write_text(text, encoding="utf-8")
        genre = genres.get(path.name, "unknown")
        row = {
            "book_id": path.name,
            "genre": genre,
            "tokens_raw": result["tokens_raw"],
            "tokens_clean": result["tokens_clean"],
            "tokens_removed": result["tokens_removed"],
            "tokens_detected_spans": result["tokens_detected_spans"],
            "tokens_shuffle_removed": shuffle_removed,
            "n_exact_hits": result["n_exact_hits"],
            "n_fuzzy_hits": result["n_fuzzy_hits"],
            "n_concat_hits": result["n_concat_hits"],
            "removed_frac": (
                result["tokens_removed"] / result["tokens_raw"] if result["tokens_raw"] else 0.0
            ),
        }
        per_book.append(row)
        g = by_genre[genre]
        g["tokens_raw"] += result["tokens_raw"]
        g["tokens_removed"] += result["tokens_removed"]
        g["tokens_detected_spans"] += result["tokens_detected_spans"]
        g["tokens_shuffle_removed"] += shuffle_removed
        g["n_books"] += 1
        if len(per_book) % 50 == 0:
            print(
                f"quotes checkpoint books={len(per_book)}/{len(books)} "
                f"removed={sum(r['tokens_removed'] for r in per_book)}",
                flush=True,
            )

        grams = token_ngrams(tokens, n)
        concat_hit_set = set(result["concat_hits"])
        for i in result["exact_hits"] + result["fuzzy_hits"] + result["concat_hits"]:
            lo = max(0, i - cfg.match_margin_tokens)
            hi = min(len(tokens), i + n + cfg.match_margin_tokens)
            if i in result["exact_hits"]:
                kind = "exact"
            elif i in result["fuzzy_hits"]:
                kind = "fuzzy"
            else:
                kind = "concat"
            add_match(
                {
                    "book_id": path.name,
                    "genre": genre,
                    "start": i,
                    "kind": kind,
                    "window": tokens[lo:hi],
                }
            )
        hit_set = set(result["exact_hits"]) | set(result["fuzzy_hits"]) | concat_hit_set
        for i, gram in enumerate(grams):
            if i in hit_set:
                continue
            add_non(
                {
                    "book_id": path.name,
                    "genre": genre,
                    "start": i,
                    "kind": "nonmatch",
                    "window": list(gram),
                }
            )

    totals = {
        "tokens_raw": sum(r["tokens_raw"] for r in per_book),
        "tokens_removed": sum(r["tokens_removed"] for r in per_book),
        "tokens_clean": sum(r["tokens_clean"] for r in per_book),
        "tokens_shuffle_removed": sum(r["tokens_shuffle_removed"] for r in per_book),
        "n_books": len(per_book),
        "n_quran_tokens": len(quran_tokens),
        "n_quran_ngrams": len(exact),
        "n_concat_needles": len(concat_needles),
    }
    report = {
        "task": "T-016",
        "quote_ngram_n": n,
        "minhash_num_perm": cfg.minhash_num_perm,
        "minhash_threshold": cfg.minhash_threshold,
        "match_margin_tokens": cfg.match_margin_tokens,
        "totals": totals,
        "by_genre": dict(by_genre),
        "per_book": per_book,
        "audit": {
            "n_matches_sampled": len(matches),
            "n_nonmatches_sampled": len(nonmatches),
            "precision": None,
            "recall_approx": None,
            "pending_human": True,
            "note": (
                "DoD T-016: reczny audyt 100 trafien i 100 nietrafien. "
                "Etykiety w results/quote_audit_sample.json (pole label)."
            ),
        },
    }
    return {
        "report": report,
        "matches": matches,
        "nonmatches": nonmatches,
        "output_dir": output_dir,
    }


def audit_is_labeled(path: Path) -> bool:
    if not path.exists():
        return False
    payload = read_json(path)
    matches = payload.get("matches") or []
    nonmatches = payload.get("nonmatches") or []
    return any(item.get("label") for item in (*matches, *nonmatches))


def summarize_audit_labels(audit: dict[str, Any]) -> dict[str, Any]:
    matches = list(audit.get("matches") or [])
    nonmatches = list(audit.get("nonmatches") or [])
    n_tp = sum(1 for m in matches if m.get("label") == "true_quote")
    n_fp = sum(1 for m in matches if m.get("label") == "false_positive")
    n_tn = sum(1 for m in nonmatches if m.get("label") == "true_negative")
    n_fn = sum(1 for m in nonmatches if m.get("label") == "missed_quote")
    n_fn_structural = sum(1 for m in nonmatches if m.get("miss_kind") == "structural_n7")
    n_labeled_m = sum(1 for m in matches if m.get("label"))
    n_labeled_n = sum(1 for m in nonmatches if m.get("label"))
    precision = (n_tp / (n_tp + n_fp)) if (n_tp + n_fp) else None
    recall_sample = (n_tn / (n_tn + n_fn)) if (n_tn + n_fn) else None
    return {
        "n_matches_sampled": len(matches),
        "n_nonmatches_sampled": len(nonmatches),
        "n_labeled_matches": n_labeled_m,
        "n_labeled_nonmatches": n_labeled_n,
        "n_true_quote": n_tp,
        "n_false_positive": n_fp,
        "n_true_negative": n_tn,
        "n_missed_quote": n_fn,
        "n_missed_structural_n7": n_fn_structural,
        "n_missed_real": n_fn - n_fn_structural,
        "precision": precision,
        "recall_sample": recall_sample,
        "recall_approx": recall_sample,
        "pending_human": n_labeled_m < len(matches) or n_labeled_n < len(nonmatches),
        "note": (
            "Audyt 2×100. precision = TP/(TP+FP) na próbce matches. "
            "recall_sample = TN/(TN+FN) na próbce nonmatches. "
            "miss_kind=structural_n7 to cytat krótszy niż quote_ngram_n — "
            "nie liczy się jako defekt metody."
        ),
    }


def write_quote_artifacts(
    payload: dict[str, Any],
    *,
    report_path: Path = QUOTE_REPORT_PATH,
    audit_path: Path = QUOTE_AUDIT_PATH,
    config_hash: str | None = None,
    preserve_labeled_audit: bool = True,
) -> dict[str, Path]:
    report = dict(payload["report"])
    report["config_hash"] = config_hash
    keep_audit = preserve_labeled_audit and audit_is_labeled(audit_path)
    if keep_audit:
        existing = read_json(audit_path)
        report["audit"] = summarize_audit_labels(existing)
        report["audit"]["source"] = "preserved_labeled_sample"
        write_json(report_path, report)
        payload["report"] = report
        return {"report": report_path, "audit": audit_path}

    write_json(report_path, report)
    write_json(
        audit_path,
        {
            "task": "T-016",
            "config_hash": config_hash,
            "matches": payload["matches"],
            "nonmatches": payload["nonmatches"],
            "label_instructions": (
                "Wpisz label: true_quote | false_positive dla matches; "
                "missed_quote | true_negative dla nonmatches."
            ),
        },
    )
    payload["report"] = report
    return {"report": report_path, "audit": audit_path}
