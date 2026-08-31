"""T-011 — selekcja autorow CTRL (docs/09_DECISIONS.md §3).

Kolejnosc krokow jest czescia decyzji (genre PRZED jakoscia).
EXCLUDE_TITLE_PATTERNS sa stosowane do ksiazek PRZED agregacja — slowniki
nie moga napelniac total_tokens. Numeracja w §3 zostawia exclude po
agregacji; intencja ('dziela bez autorskiego glosu') wymaga odwrotnej
kolejnosci operacyjnej.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from src.data.download_openiti import load_metadata, raw_text_url
from src.data.genre import assign_genre_two_stage, is_excluded_title
from src.data.quality_cache import QUALITY_CACHE_PATH, collect_quality_metrics, fetch_text_bytes
from src.data.quality_proxy import QualityMetrics, passes_quality_thresholds
from src.paths import CTRL_MANIFEST_PATH, DATA_RAW_DIR, RESULTS_DIR
from src.utils.io import ensure_dir, write_json
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)

HARD_MINIMA: dict[str, int] = {
    "maqamat_saj": 3,
    "poetry_diwan": 5,
    "prayer_sermon": 2,
    "hadith_collection": 2,
}
MAX_AUTHORS_PER_GENRE = 12
TOKEN_THRESHOLD_PRIMARY = 30_000
TOKEN_THRESHOLD_RELAXED = 20_000
MIN_BOOKS = 2
MIN_MAX_BOOK_TOKENS = 10_000
SINGLE_WORK_MIN_TOKENS = 15_000
SINGLE_WORK_EXCEPTION_GENRES = frozenset(HARD_MINIMA)
MIN_AUTHORS = 60
SOFT_OTHER_SHARE = 0.50
SELECTED_TEXT_DIR: Path = DATA_RAW_DIR / "openiti" / "selected"


def candidate_pool(df: pd.DataFrame) -> pd.DataFrame:
    """Kroki 1–2 §3: pri + CLEANED_VERSION + language==ara + 0 < death <= 900."""
    return df.loc[
        df.is_pri
        & df.is_arabic
        & df.has_cleaned_tag
        & (df.death_date_ah > 0)
        & (df.death_date_ah <= 900)
    ].copy()


def assign_genres(pool: pd.DataFrame, *, map_path: str | None = None) -> pd.DataFrame:
    """Krok 3: gatunek na ksiazke (tagi, potem tytul, potem other)."""
    out = pool.copy()
    assignments = [
        assign_genre_two_stage(
            tags=str(row.tags),
            title_lat=str(row.title_lat),
            title_ar=str(row.title_ar),
            book=str(row.book),
            map_path=map_path,
        )
        for row in out.itertuples()
    ]
    out["genre"] = [a.genre for a in assignments]
    out["genre_source"] = [a.source for a in assignments]
    return out


def apply_quality(
    pool: pd.DataFrame,
    cache: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    """Krok 4: filtr gatunkowo-zalezny. Brak pobrania = fail (nie zgadujemy)."""
    records: list[dict[str, Any]] = []
    for row in pool.itertuples():
        rec = cache.get(str(row.version_uri), {})
        http_ok = bool(rec.get("http_ok"))
        non_ar = rec.get("non_arabic_ratio")
        mean_len = rec.get("mean_word_length")
        passed = False
        if http_ok and non_ar is not None and mean_len is not None:
            metrics = QualityMetrics(
                n_chars_raw=0,
                n_chars_clean=0,
                n_markdown_chars_removed=int(rec.get("n_markdown_chars_removed") or 0),
                n_lines=0,
                n_long_lines=0,
                non_arabic_ratio=float(non_ar),
                mean_word_length=float(mean_len),
                long_line_ratio=float(rec.get("long_line_ratio") or 0.0),
                n_words=int(rec.get("n_words") or 0),
            )
            passed = passes_quality_thresholds(metrics, genre=str(row.genre))
        records.append(
            {
                "version_uri": row.version_uri,
                "quality_http_ok": http_ok,
                "non_arabic_ratio": non_ar,
                "mean_word_length": mean_len,
                "long_line_ratio": rec.get("long_line_ratio"),
                "n_markdown_chars_removed": rec.get("n_markdown_chars_removed"),
                "quality_passed": passed,
            }
        )
    qdf = pd.DataFrame.from_records(records)
    merged = pool.merge(qdf, on="version_uri", how="left")
    return merged.loc[merged["quality_passed"] == True].copy()  # noqa: E712


def drop_excluded_titles(pool: pd.DataFrame) -> pd.DataFrame:
    """Krok 6 §3, wykonany PRZED agregacja (slowniki nie inflatuja tokenow)."""
    mask = [
        not is_excluded_title(
            title_lat=str(row.title_lat),
            title_ar=str(row.title_ar),
            book=str(row.book),
        )
        for row in pool.itertuples()
    ]
    return pool.loc[mask].copy()


def _primary_genre(grp: pd.DataFrame, genre_rank: dict[str, int]) -> str:
    by_genre = grp.groupby("genre", sort=False)["tok_length_n"].sum()
    return sorted(
        by_genre.items(),
        key=lambda kv: (-kv[1], genre_rank.get(str(kv[0]), 99)),
    )[0][0]


def admission_path_for(
    *,
    n_books: int,
    total_tokens: float,
    max_book_tokens: float,
    author_genre: str,
    min_total_tokens: int,
) -> str | None:
    """Krok 5 §3. None = autor nie wchodzi.

    PSEUDO-BOOK (T-034 / 03_DATA §11) i tak wymaga n_books>=2 — sciezka
    single_work_exception odpada tam sama, bez drugiego filtra tutaj.
    """
    if n_books >= MIN_BOOKS and total_tokens >= min_total_tokens and max_book_tokens >= MIN_MAX_BOOK_TOKENS:
        return "standard"
    if (
        n_books == 1
        and max_book_tokens >= SINGLE_WORK_MIN_TOKENS
        and author_genre in SINGLE_WORK_EXCEPTION_GENRES
    ):
        return "single_work_exception"
    return None


def aggregate_authors(
    books: pd.DataFrame,
    *,
    min_total_tokens: int = TOKEN_THRESHOLD_PRIMARY,
) -> pd.DataFrame:
    """Krok 5: standard LUB wyjątek jednodzielowy dla gatunkow z twardym minimum."""
    from src.data.genre import _GENRE_RULES

    genre_rank = {label: i for i, (label, _) in enumerate(_GENRE_RULES)}
    genre_rank.setdefault("other", len(genre_rank))

    work = books.copy()
    work["tok_length_n"] = pd.to_numeric(work["tok_length_n"], errors="coerce").fillna(0.0)
    rows: list[dict[str, Any]] = []
    for author_id, grp in work.groupby("author_id", sort=True):
        n_books = int(grp["book"].nunique())
        total = float(grp["tok_length_n"].sum())
        max_book = float(grp["tok_length_n"].max()) if len(grp) else 0.0
        primary = _primary_genre(grp, genre_rank)
        path = admission_path_for(
            n_books=n_books,
            total_tokens=total,
            max_book_tokens=max_book,
            author_genre=str(primary),
            min_total_tokens=min_total_tokens,
        )
        if path is None:
            continue
        death = float(grp["death_date_ah"].min())
        layer = "near-period" if death <= 500 else "broad"
        rows.append(
            {
                "author_id": author_id,
                "author_lat": str(grp["author_lat"].iloc[0]) if "author_lat" in grp else "",
                "death_date_ah": death,
                "layer": layer,
                "n_books": n_books,
                "total_tokens": total,
                "max_book_tokens": max_book,
                "author_genre": primary,
                "genres_present": " ".join(sorted(set(grp["genre"].astype(str)))),
                "admission_path": path,
            }
        )
    return pd.DataFrame(rows)


def _take_up_to_n_per_genre(authors: pd.DataFrame, n: int) -> pd.DataFrame:
    """Kroki 7–8: sort total_tokens desc w gatunku, max `n` autorow na gatunek."""
    if authors.empty:
        return authors
    picked: list[pd.DataFrame] = []
    for genre, grp in authors.groupby("author_genre", sort=True):
        ordered = grp.sort_values(["total_tokens", "author_id"], ascending=[False, True])
        picked.append(ordered.head(n))
    return pd.concat(picked, ignore_index=True)


def _has_genre(series: pd.Series, genre: str) -> pd.Series:
    """Autor 'ma' gatunek, jesli jest wksrod jego ksiazek — nie tylko primary."""
    return series.fillna("").map(lambda s: genre in str(s).split())


def coverage_counts(authors: pd.DataFrame) -> dict[str, int]:
    """Licznik twardych minimow: autorzy z >=1 ksiazka danego gatunku."""
    if authors.empty:
        return {genre: 0 for genre in HARD_MINIMA}
    return {genre: int(_has_genre(authors["genres_present"], genre).sum()) for genre in HARD_MINIMA}


def _pull_coverage(
    selected: pd.DataFrame,
    eligible: pd.DataFrame,
) -> pd.DataFrame:
    """Regula pokrycia §4: dociagnij autorow brakujacych gatunkow, ignorujac krok 8.

    Minimum liczy autorow, ktorzy MAJA ksiazke gatunku (takze jako gatunek
    uboczny). Inaczej Hariri (Maqamat + wiekszy inny tom) wypada z maqamat_saj.
    """
    have = selected["author_id"].astype(str).tolist() if not selected.empty else []
    out = selected.copy() if not selected.empty else eligible.iloc[0:0].copy()
    for genre, minimum in HARD_MINIMA.items():
        n_have = int(_has_genre(out["genres_present"], genre).sum()) if not out.empty else 0
        if n_have >= minimum:
            continue
        extra = eligible.loc[
            _has_genre(eligible["genres_present"], genre) & ~eligible["author_id"].isin(have)
        ].sort_values(["total_tokens", "author_id"], ascending=[False, True])
        need = minimum - n_have
        add = extra.head(need)
        if not add.empty:
            out = pd.concat([out, add], ignore_index=True)
            have.extend(add["author_id"].astype(str).tolist())
    return out


@dataclass
class SelectionResult:
    authors: pd.DataFrame
    books: pd.DataFrame
    relaxed_to_20000: bool
    n_authors: int
    genre_counts: dict[str, int] = field(default_factory=dict)
    coverage_counts: dict[str, int] = field(default_factory=dict)
    other_share: float = 0.0
    minima_ok: bool = False
    authors_ok: bool = False
    blocked: bool = False
    notes: list[str] = field(default_factory=list)
    exception_counts: dict[str, int] = field(default_factory=dict)
    n_single_work_exception: int = 0


def select_authors(eligible_books: pd.DataFrame) -> SelectionResult:
    """Kroki 5, 7–9 + regula pokrycia. Wejscie: ksiazki po jakosci i exclude."""
    notes: list[str] = []
    authors_30 = aggregate_authors(eligible_books, min_total_tokens=TOKEN_THRESHOLD_PRIMARY)
    picked = _take_up_to_n_per_genre(authors_30, MAX_AUTHORS_PER_GENRE)
    relaxed = False
    eligible_authors = authors_30

    if len(picked) < MIN_AUTHORS:
        notes.append(
            f"po progu {TOKEN_THRESHOLD_PRIMARY} i cap {MAX_AUTHORS_PER_GENRE}: "
            f"{len(picked)} autorow — luzuje do {TOKEN_THRESHOLD_RELAXED}"
        )
        authors_20 = aggregate_authors(eligible_books, min_total_tokens=TOKEN_THRESHOLD_RELAXED)
        picked = _take_up_to_n_per_genre(authors_20, MAX_AUTHORS_PER_GENRE)
        eligible_authors = authors_20
        relaxed = True
    else:
        notes.append(
            f"prog {TOKEN_THRESHOLD_PRIMARY} wystarczyl "
            f"({len(authors_30)} eligible, {len(picked)} po cap)"
        )

    picked = _pull_coverage(picked, eligible_authors)
    counts = (
        picked["author_genre"].value_counts().sort_index().to_dict() if not picked.empty else {}
    )
    counts = {str(k): int(v) for k, v in counts.items()}
    cover = coverage_counts(picked)
    if picked.empty or "admission_path" not in picked.columns:
        exception_by_genre: dict[str, int] = {}
        n_exc = 0
    else:
        exc = picked.loc[picked["admission_path"] == "single_work_exception"]
        exception_by_genre = (
            exc["author_genre"].value_counts().sort_index().astype(int).to_dict() if not exc.empty else {}
        )
        exception_by_genre = {str(k): int(v) for k, v in exception_by_genre.items()}
        n_exc = int(len(exc))
    n_authors = int(len(picked))
    other_share = (counts.get("other", 0) / n_authors) if n_authors else 1.0
    minima_ok = all(cover.get(g, 0) >= m for g, m in HARD_MINIMA.items())
    authors_ok = n_authors >= MIN_AUTHORS
    blocked = (not authors_ok) or (not minima_ok)
    if not minima_ok:
        missing = {g: HARD_MINIMA[g] - cover.get(g, 0) for g in HARD_MINIMA if cover.get(g, 0) < HARD_MINIMA[g]}
        notes.append(f"brak twardego minimum: {missing}")
    if not authors_ok:
        notes.append(f"autorow {n_authors} < {MIN_AUTHORS}")

    if picked.empty:
        books = eligible_books.iloc[0:0].copy()
    else:
        books = eligible_books.loc[eligible_books["author_id"].isin(picked["author_id"])].copy()
        books = books.merge(
            picked[
                [
                    "author_id",
                    "author_genre",
                    "genres_present",
                    "n_books",
                    "total_tokens",
                    "max_book_tokens",
                    "layer",
                    "admission_path",
                ]
            ],
            on="author_id",
            how="left",
        )
    return SelectionResult(
        authors=picked,
        books=books,
        relaxed_to_20000=relaxed,
        n_authors=n_authors,
        genre_counts=counts,
        coverage_counts=cover,
        other_share=other_share,
        minima_ok=minima_ok,
        authors_ok=authors_ok,
        blocked=blocked,
        notes=notes,
        exception_counts=exception_by_genre,
        n_single_work_exception=n_exc,
    )


def _download_one_selected(row: pd.Series, dest: Path) -> tuple[bool, int, str]:
    url = raw_text_url(row)
    uri = str(row["version_uri"]).replace("/", "_")
    path = dest / uri
    if path.is_file() and path.stat().st_size > 0:
        return True, path.stat().st_size, ""
    status, blob, error = fetch_text_bytes(url)
    if blob is None:
        LOGGER.warning("selected text fail", extra={"url": url, "error": error, "status": status})
        return False, 0, error or f"HTTP {status}"
    path.write_bytes(blob)
    return True, len(blob), ""


def _download_selected_texts(books: pd.DataFrame, dest: Path, *, workers: int = 8) -> dict[str, Any]:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    ensure_dir(dest)
    n_ok = 0
    n_fail = 0
    n_bytes = 0
    n_total = int(len(books))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_download_one_selected, row, dest): str(row["version_uri"])
            for _, row in books.iterrows()
        }
        done = 0
        for future in as_completed(futures):
            ok, nbytes, _err = future.result()
            done += 1
            if ok:
                n_ok += 1
                n_bytes += nbytes
            else:
                n_fail += 1
            if done % 50 == 0 or done == n_total:
                print(f"selected texts {done}/{n_total}", flush=True)
    return {
        "n_expected": n_total,
        "n_downloaded": n_ok,
        "n_failed": n_fail,
        "n_bytes": n_bytes,
        "n_gib": round(n_bytes / (1024**3), 3),
        "n_authors": int(books["author_id"].nunique()) if n_total else 0,
        "dest": str(dest.as_posix()),
    }


def write_manifest(books: pd.DataFrame, path: Path = CTRL_MANIFEST_PATH) -> Path:
    ensure_dir(path.parent)
    cols = [
        c
        for c in (
            "author_id",
            "author_lat",
            "author_ar",
            "death_date_ah",
            "layer",
            "book",
            "version_uri",
            "title_lat",
            "title_ar",
            "genre",
            "genre_source",
            "author_genre",
            "genres_present",
            "tok_length_n",
            "n_books",
            "total_tokens",
            "max_book_tokens",
            "admission_path",
            "quality_passed",
            "non_arabic_ratio",
            "mean_word_length",
            "n_markdown_chars_removed",
            "uncorrected_ocr",
            "local_path",
            "tags",
        )
        if c in books.columns
    ]
    books.loc[:, cols].sort_values(["author_genre", "author_id", "book"]).to_csv(
        path, index=False, encoding="utf-8", lineterminator="\n"
    )
    return path


def run_select_ctrl(
    *,
    metadata_path: Path | None = None,
    manifest_path: Path = CTRL_MANIFEST_PATH,
    cache_path: Path = QUALITY_CACHE_PATH,
    workers: int = 8,
    download_texts: bool = True,
    map_path: str | None = None,
) -> dict[str, Any]:
    """Pelny algorytm §3. Siec tylko do metryk jakosci i (opcjonalnie) tekstow."""
    df = load_metadata(metadata_path)
    pool = candidate_pool(df)
    pool = assign_genres(pool, map_path=map_path)
    cache = collect_quality_metrics(pool, cache_path=cache_path, workers=workers)
    after_quality = apply_quality(pool, cache)
    after_exclude = drop_excluded_titles(after_quality)
    result = select_authors(after_exclude)

    summary: dict[str, Any] = {
        "n_metadata": int(len(df)),
        "n_candidate_pool": int(len(pool)),
        "n_after_quality": int(len(after_quality)),
        "n_after_exclude": int(len(after_exclude)),
        "n_authors": result.n_authors,
        "n_books_selected": int(len(result.books)),
        "genre_counts": result.genre_counts,
        "coverage_counts": result.coverage_counts,
        "exception_counts": result.exception_counts,
        "n_single_work_exception": result.n_single_work_exception,
        "hard_minima": HARD_MINIMA,
        "minima_ok": result.minima_ok,
        "authors_ok": result.authors_ok,
        "other_share": result.other_share,
        "other_share_soft_target": SOFT_OTHER_SHARE,
        "other_share_below_soft_target": result.other_share < SOFT_OTHER_SHARE,
        "relaxed_to_20000": result.relaxed_to_20000,
        "token_threshold_used": (
            TOKEN_THRESHOLD_RELAXED if result.relaxed_to_20000 else TOKEN_THRESHOLD_PRIMARY
        ),
        "blocked": result.blocked,
        "notes": result.notes,
        "genre_source_counts": after_exclude["genre_source"]
        .str.split(":")
        .str[0]
        .value_counts()
        .to_dict()
        if not after_exclude.empty
        else {},
        "download": None,
    }
    # genre_source_counts values to int
    summary["genre_source_counts"] = {str(k): int(v) for k, v in summary["genre_source_counts"].items()}

    if not result.blocked:
        write_manifest(result.books, manifest_path)
        summary["manifest"] = str(manifest_path.as_posix())
        if download_texts and not result.books.empty:
            summary["download"] = _download_selected_texts(result.books, SELECTED_TEXT_DIR)
    else:
        summary["manifest"] = None

    write_json(RESULTS_DIR / "ctrl_selection.json", summary)
    return summary
