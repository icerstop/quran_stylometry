"""T-017: redundancja wewnetrzna (docs/03_DATA.md §7b).

``internal_duplication_rate`` = odsetek *typów* 7-gramów z count ≥ 2 w obrębie
korpusu (albo gatunku). Wariant ``dedup=true`` zostawia pierwsze wystapienie
kazdego typu i wycina tokeny, ktore naleza wylacznie do pozniejszych.

Nie miesza sie z T-016 (cytaty Koranu w CTRL): tu oba korpusy sa liczone
osobno, na wlasnych 7-gramach.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data.detect_quran_quotes import (
    EQTB_TOKENS_PATH,
    load_genre_map,
    quran_ortho_words,
    token_ngrams,
)
from src.paths import (
    GENRES_PATH,
    INTERNAL_DUP_PATH,
    OPENITI_CLEAN_DIR,
    OPENITI_DEDUP_DIR,
    rel_to_repo,
)
from src.utils.io import ensure_dir, write_json
from src.utils.seed import new_rng

NGRAM_SEP = "\x1f"


def ngram_key(gram: Sequence[str]) -> str:
    return NGRAM_SEP.join(gram)


def count_ngrams(tokens: Sequence[str], n: int) -> Counter[str]:
    counts: Counter[str] = Counter()
    if n <= 0 or len(tokens) < n:
        return counts
    for i in range(len(tokens) - n + 1):
        counts[ngram_key(tokens[i : i + n])] += 1
    return counts


def duplication_stats(counts: Counter[str]) -> dict[str, float | int]:
    n_types = len(counts)
    n_ge2 = sum(1 for c in counts.values() if c >= 2)
    n_inst = int(sum(counts.values()))
    mass_ge2 = int(sum(c for c in counts.values() if c >= 2))
    return {
        "n_types": n_types,
        "n_types_ge2": n_ge2,
        "internal_duplication_rate": (n_ge2 / n_types) if n_types else 0.0,
        "n_instances": n_inst,
        "instance_mass_ge2": (mass_ge2 / n_inst) if n_inst else 0.0,
    }


def dedup_tokens(tokens: Sequence[str], n: int) -> list[str]:
    """Greedy: pierwsze wystapienie typu zostaje; pozniejsze n tokenow omijamy."""
    seq = list(tokens)
    if n <= 0 or len(seq) < n:
        return seq
    seen: set[str] = set()
    out: list[str] = []
    i = 0
    while i < len(seq):
        if i + n <= len(seq):
            key = ngram_key(seq[i : i + n])
            if key in seen:
                i += n
                continue
            seen.add(key)
        out.append(seq[i])
        i += 1
    return out


def dedup_tokens_global(tokens: Sequence[str], n: int, seen: set[str]) -> list[str]:
    """Jak ``dedup_tokens``, ale dzieli zbior typow miedzy jednostkami."""
    seq = list(tokens)
    if n <= 0 or len(seq) < n:
        return seq
    out: list[str] = []
    i = 0
    while i < len(seq):
        if i + n <= len(seq):
            key = ngram_key(seq[i : i + n])
            if key in seen:
                i += n
                continue
            seen.add(key)
        out.append(seq[i])
        i += 1
    return out


def shuffle_tokens(tokens: Sequence[str], rng: np.random.Generator) -> list[str]:
    if not tokens:
        return []
    order = rng.permutation(len(tokens))
    return [tokens[int(i)] for i in order]


def _unit_rate(tokens: Sequence[str], n: int) -> float:
    stats = duplication_stats(count_ngrams(tokens, n))
    return float(stats["internal_duplication_rate"])


def _mean_std(values: Sequence[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    arr = np.asarray(values, dtype=float)
    mean = float(arr.mean())
    std = float(arr.std(ddof=1)) if len(arr) >= 2 else 0.0
    return mean, std


def _list_ctrl_books(input_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in input_dir.iterdir()
        if p.is_file() and p.name != "manifest.csv" and not p.name.endswith(".done")
    )


def measure_corpus(
    units: Sequence[tuple[str, list[str]]],
    *,
    n: int,
    rng: np.random.Generator,
    write_dedup_dir: Path | None = None,
) -> dict[str, Any]:
    """units = (unit_id, tokens). Pula = caly korpus; wasy = SD po jednostkach."""
    pooled: Counter[str] = Counter()
    unit_rates: list[float] = []
    n_tokens = 0
    n_tokens_dedup = 0
    shuffle_pooled: Counter[str] = Counter()
    shuffle_unit_rates: list[float] = []
    seen_global: set[str] = set()
    remaining: Counter[str] = Counter()

    if write_dedup_dir is not None:
        ensure_dir(write_dedup_dir)

    for unit_id, tokens in units:
        n_tokens += len(tokens)
        counts = count_ngrams(tokens, n)
        pooled.update(counts)
        unit_rates.append(_unit_rate(tokens, n))
        shuffled = shuffle_tokens(tokens, rng)
        shuffle_pooled.update(count_ngrams(shuffled, n))
        shuffle_unit_rates.append(_unit_rate(shuffled, n))

        kept = dedup_tokens_global(tokens, n, seen_global)
        n_tokens_dedup += len(kept)
        remaining.update(count_ngrams(kept, n))
        if write_dedup_dir is not None:
            text = " ".join(kept) + ("\n" if kept else "")
            (write_dedup_dir / unit_id).write_text(text, encoding="utf-8")

    raw = duplication_stats(pooled)
    shuf = duplication_stats(shuffle_pooled)
    rem = duplication_stats(remaining)
    mean_u, std_u = _mean_std(unit_rates)
    mean_s, std_s = _mean_std(shuffle_unit_rates)
    return {
        "n_units": len(units),
        "n_tokens": n_tokens,
        "n_tokens_dedup": n_tokens_dedup,
        "raw": raw,
        "dedup": {
            "n_tokens": n_tokens_dedup,
            "token_kept_frac": (n_tokens_dedup / n_tokens) if n_tokens else 0.0,
            "internal_duplication_rate": rem["internal_duplication_rate"],
            "n_types": rem["n_types"],
            "n_types_ge2": rem["n_types_ge2"],
        },
        "shuffle": shuf,
        "unit_rate_mean": mean_u,
        "unit_rate_std": std_u,
        "shuffle_unit_rate_mean": mean_s,
        "shuffle_unit_rate_std": std_s,
    }


def run_internal_duplication(
    *,
    n: int,
    seed: int,
    eqtb_path: Path = EQTB_TOKENS_PATH,
    ctrl_dir: Path = OPENITI_CLEAN_DIR,
    genre_map: dict[str, str] | None = None,
    limit_books: int | None = None,
    write_dedup: bool = True,
    profile: str = "strict",
) -> dict[str, Any]:
    if not eqtb_path.exists():
        raise FileNotFoundError(f"Brak {eqtb_path} (T-009)")
    if not ctrl_dir.is_dir():
        raise FileNotFoundError(f"Brak {ctrl_dir} (T-016)")

    eqtb = pd.read_parquet(eqtb_path)
    words = quran_ortho_words(eqtb, profile=profile)
    by_surah: dict[int, list[str]] = defaultdict(list)
    quran_tokens: list[str] = []
    for word in words:
        by_surah[word.surah_id].append(word.token)
        quran_tokens.append(word.token)
    quran_units = [(f"s{sid:03d}", toks) for sid, toks in sorted(by_surah.items())]

    genres = genre_map if genre_map is not None else load_genre_map(GENRES_PATH)
    books = _list_ctrl_books(ctrl_dir)
    if limit_books is not None:
        books = books[: int(limit_books)]
    ctrl_units: list[tuple[str, list[str]]] = []
    by_genre_units: dict[str, list[tuple[str, list[str]]]] = defaultdict(list)
    for path in books:
        tokens = path.read_text(encoding="utf-8").split()
        unit = (path.name, tokens)
        ctrl_units.append(unit)
        genre = genres.get(path.name, "other")
        by_genre_units[genre].append(unit)

    rng_q = new_rng(seed, "t017_quran")
    rng_c = new_rng(seed, "t017_ctrl")
    dedup_dir = OPENITI_DEDUP_DIR if write_dedup else None
    quran = measure_corpus(quran_units, n=n, rng=rng_q, write_dedup_dir=None)
    # Quran dedup rate: in-memory, nie zapisujemy pliku w data/ (poza reference).
    quran_kept = dedup_tokens(quran_tokens, n)
    quran["n_tokens_dedup"] = len(quran_kept)
    quran["dedup"] = {
        "n_tokens": len(quran_kept),
        "token_kept_frac": (len(quran_kept) / len(quran_tokens)) if quran_tokens else 0.0,
        **duplication_stats(count_ngrams(quran_kept, n)),
    }

    ctrl = measure_corpus(ctrl_units, n=n, rng=rng_c, write_dedup_dir=dedup_dir)
    by_genre: dict[str, Any] = {}
    for genre, units in sorted(by_genre_units.items()):
        rng_g = new_rng(seed, f"t017_genre_{genre}")
        by_genre[genre] = measure_corpus(units, n=n, rng=rng_g, write_dedup_dir=None)

    return {
        "task": "T-017",
        "quote_ngram_n": n,
        "n_ctrl_books": len(ctrl_units),
        "quran": quran,
        "ctrl": ctrl,
        "by_genre": by_genre,
        "dedup_dir": rel_to_repo(dedup_dir) if dedup_dir is not None else None,
    }


def write_duplication_report(
    payload: dict[str, Any],
    *,
    path: Path = INTERNAL_DUP_PATH,
    config_hash: str | None = None,
) -> Path:
    out = dict(payload)
    out["config_hash"] = config_hash
    write_json(path, out)
    return path
