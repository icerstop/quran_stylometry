"""Limit 200 000 tokenow per autor (docs/09_DECISIONS.md §3).

Krok miedzy T-013 a T-015. Wejscie: surowe pliki CTRL + ``normalize(strict)``
(T-013 jest juz zaimplementowane — nie uruchamiamy ponownie benchmarku).
Alokacja limitu proporcjonalna do liczby tokenow per dzielo; w kazdym dziele
losowy ciagly fragment, nigdy prefiks. Seed z configu (T-004 / ``new_rng``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data.normalize_arabic import normalize
from src.data.select_ctrl import SELECTED_TEXT_DIR
from src.paths import CTRL_CAPPED_DIR, CTRL_MANIFEST_PATH, RESULTS_DIR
from src.utils.io import ensure_dir, write_json
from src.utils.seed import new_rng

DEFAULT_LIMIT = 200_000
CAPPED_DIR: Path = CTRL_CAPPED_DIR
CAPPED_MANIFEST_PATH: Path = CTRL_CAPPED_DIR / "manifest.csv"
CAP_SUMMARY_PATH: Path = RESULTS_DIR / "ctrl_cap.json"


@dataclass(frozen=True)
class BookCap:
    author_id: str
    book_id: str
    version_uri: str
    tokens_before_cap: int
    tokens_after_cap: int
    span_seed: int
    span_start: int


def allocate_proportional(counts: list[int], limit: int) -> list[int]:
    """Hamilton / largest remainder, z gwarancja >=1 dla kazdego dziela z count>0.

    Suma wyniku = min(sum(counts), limit). Zadne dzielo z dodatnia liczba
    tokenow nie dostaje zera — sanity check z decyzji §3.
    """
    if limit < 0:
        raise ValueError(f"limit musi byc >= 0, dostano {limit}")
    total = sum(counts)
    if total <= limit:
        return list(counts)
    positive = [i for i, count in enumerate(counts) if count > 0]
    if len(positive) > limit:
        raise ValueError(
            f"limit={limit} jest mniejszy niz liczba dziel ({len(positive)}) — "
            "nie da sie zachowac niezerowej alokacji"
        )

    exact = [limit * count / total for count in counts]
    result = [min(count, int(share)) for count, share in zip(counts, exact, strict=True)]
    for i in positive:
        if result[i] == 0:
            result[i] = 1

    def _steal() -> None:
        while sum(result) > limit:
            donors = [i for i in positive if result[i] > 1]
            if not donors:
                break
            i = max(donors, key=lambda j: result[j])
            result[i] -= 1

    def _give() -> None:
        while sum(result) < limit:
            room = [i for i in positive if result[i] < counts[i]]
            if not room:
                break
            i = max(room, key=lambda j: (exact[j] - int(exact[j]), -j))
            result[i] += 1

    _steal()
    _give()
    return result


def span_start(n_tokens: int, n_keep: int, span_seed: int) -> int:
    """Poczatek ciaglego fragmentu. Pelne dzielo => 0; w przeciwnym razie U{0..n-k}."""
    if n_keep <= 0:
        return 0
    if n_keep >= n_tokens:
        return 0
    rng = np.random.default_rng(span_seed)
    return int(rng.integers(0, n_tokens - n_keep + 1))


def book_span_seed(config_seed: int, author_id: str, book_id: str) -> int:
    rng = new_rng(config_seed, stream=f"ctrl_cap:{author_id}:{book_id}")
    return int(rng.integers(0, 2**31 - 1))


def slice_tokens(tokens: list[str], n_keep: int, span_seed: int) -> tuple[list[str], int]:
    start = span_start(len(tokens), n_keep, span_seed)
    return tokens[start : start + n_keep], start


def cap_author_books(
    books: list[tuple[str, list[str]]],
    *,
    author_id: str,
    limit: int,
    config_seed: int,
) -> list[tuple[str, list[str], BookCap]]:
    """``books`` = lista (book_id, tokens). Zwraca (book_id, capped_tokens, meta)."""
    counts = [len(toks) for _, toks in books]
    after = allocate_proportional(counts, limit)
    out: list[tuple[str, list[str], BookCap]] = []
    for (book_id, tokens), n_before, n_after in zip(books, counts, after, strict=True):
        seed = book_span_seed(config_seed, author_id, book_id)
        capped, start = slice_tokens(tokens, n_after, seed)
        meta = BookCap(
            author_id=author_id,
            book_id=book_id,
            version_uri="",
            tokens_before_cap=n_before,
            tokens_after_cap=len(capped),
            span_seed=seed,
            span_start=start,
        )
        out.append((book_id, capped, meta))
    return out


def _load_normalized_tokens(path: Path, profile: str) -> list[str]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    text = normalize(raw, profile)  # type: ignore[arg-type]
    return text.split() if text else []


def run_ctrl_cap(
    *,
    limit: int = DEFAULT_LIMIT,
    config_seed: int = 20260830,
    profile: str = "strict",
    manifest_path: Path = CTRL_MANIFEST_PATH,
    selected_dir: Path = SELECTED_TEXT_DIR,
    out_dir: Path = CAPPED_DIR,
    summary_path: Path = CAP_SUMMARY_PATH,
) -> dict[str, Any]:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Brak {manifest_path} — najpierw T-011.")
    if not selected_dir.is_dir():
        raise FileNotFoundError(f"Brak {selected_dir} — najpierw T-011 download.")

    manifest = pd.read_csv(manifest_path, dtype={"version_uri": str, "author_id": str, "book": str})
    ensure_dir(out_dir)
    rows: list[dict[str, Any]] = []
    n_files = 0
    n_authors = int(manifest["author_id"].nunique())

    for author_id, group in manifest.groupby("author_id", sort=True):
        books: list[tuple[str, list[str]]] = []
        uris: list[str] = []
        for rec in group.itertuples(index=False):
            uri = str(rec.version_uri)
            book_id = str(rec.book)
            src = selected_dir / uri
            if not src.is_file():
                raise FileNotFoundError(f"Brak tekstu CTRL: {src}")
            tokens = _load_normalized_tokens(src, profile)
            books.append((book_id, tokens))
            uris.append(uri)
            n_files += 1
            if n_files % 100 == 0:
                print(f"cap-ctrl {n_files}/{len(manifest)}", flush=True)

        capped = cap_author_books(
            books, author_id=str(author_id), limit=limit, config_seed=config_seed
        )
        for uri, (_book_id, tokens, meta) in zip(uris, capped, strict=True):
            dest = out_dir / uri
            dest.write_text(" ".join(tokens) + ("\n" if tokens else ""), encoding="utf-8")
            rows.append(
                {
                    "author_id": meta.author_id,
                    "book_id": meta.book_id,
                    "version_uri": uri,
                    "tokens_before_cap": meta.tokens_before_cap,
                    "tokens_after_cap": meta.tokens_after_cap,
                    "span_seed": meta.span_seed,
                    "span_start": meta.span_start,
                }
            )

    out_df = pd.DataFrame(rows)
    out_manifest = out_dir / "manifest.csv"
    out_df.to_csv(out_manifest, index=False, encoding="utf-8", lineterminator="\n")

    per_author = (
        out_df.groupby("author_id", sort=False)
        .agg(
            tokens_before=("tokens_before_cap", "sum"),
            tokens_after=("tokens_after_cap", "sum"),
            n_books=("book_id", "size"),
            max_book_before=("tokens_before_cap", "max"),
            max_book_after=("tokens_after_cap", "max"),
            min_book_after=("tokens_after_cap", "min"),
        )
        .reset_index()
    )
    clipped = per_author.loc[per_author["tokens_before"] > limit]
    n_clipped = int(len(clipped))
    n_zero_books = int((out_df["tokens_after_cap"] == 0).sum())
    n_zero_from_positive = int(
        ((out_df["tokens_before_cap"] > 0) & (out_df["tokens_after_cap"] == 0)).sum()
    )
    author_ge_max_book_after = bool(
        (per_author["tokens_after"] >= per_author["max_book_after"]).all()
    )
    no_book_zeroed = n_zero_from_positive == 0

    summary: dict[str, Any] = {
        "limit": limit,
        "n_authors": n_authors,
        "n_books": int(len(out_df)),
        "tokens_before": int(out_df["tokens_before_cap"].sum()),
        "tokens_after": int(out_df["tokens_after_cap"].sum()),
        "n_authors_clipped": n_clipped,
        "n_authors_uncapped": n_authors - n_clipped,
        "n_books_zeroed": n_zero_from_positive,
        "n_books_empty": n_zero_books,
        "min_book_after_among_positive": (
            int(out_df.loc[out_df["tokens_before_cap"] > 0, "tokens_after_cap"].min())
            if len(out_df)
            else 0
        ),
        "sanity_no_book_zeroed": no_book_zeroed,
        "sanity_author_total_ge_max_book_after": author_ge_max_book_after,
        "config_seed": config_seed,
        "normalizer_profile": profile,
        "out_dir": str(out_dir.as_posix()),
        "manifest": str(out_manifest.as_posix()),
    }
    write_json(summary_path, summary)
    return summary
