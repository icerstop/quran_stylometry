"""Selekcja CTRL — algorytm §3 na syntetycznych metadanych (bez sieci)."""

from __future__ import annotations

import pandas as pd

from src.data.select_ctrl import (
    HARD_MINIMA,
    aggregate_authors,
    drop_excluded_titles,
    select_authors,
)


def _book(
    author: str,
    book: str,
    tokens: int,
    genre: str,
    *,
    title_lat: str | None = None,
    death: float = 200.0,
) -> dict:
    return {
        "author_id": author,
        "author_lat": author,
        "book": book,
        "version_uri": book,
        "title_lat": title_lat if title_lat is not None else book,
        "title_ar": "",
        "genre": genre,
        "genre_source": "title",
        "tok_length_n": tokens,
        "death_date_ah": death,
        "tags": "",
    }


def test_exclude_drops_dictionary_before_aggregation() -> None:
    books = pd.DataFrame(
        [
            _book("lex", "lex.Qamus", 80_000, "other", title_lat="al-Qamus al-Muhit"),
            _book("lex", "lex.Adab", 25_000, "adab_prose", title_lat="Adab al-Katib"),
        ]
    )
    kept = drop_excluded_titles(books)
    assert len(kept) == 1
    assert kept.iloc[0]["book"] == "lex.Adab"
    authors = aggregate_authors(kept, min_total_tokens=20_000)
    assert authors.empty  # jedno dzielo — n_books < 2


def test_aggregate_keeps_author_at_30000_with_two_books() -> None:
    books = pd.DataFrame(
        [
            _book("a1", "a1.Tafsir", 20_000, "tafsir"),
            _book("a1", "a1.Fiqh", 15_000, "fiqh"),
        ]
    )
    authors = aggregate_authors(books, min_total_tokens=30_000)
    assert list(authors["author_id"]) == ["a1"]
    assert authors.iloc[0]["author_genre"] == "tafsir"  # wiecej tokenow
    assert authors.iloc[0]["layer"] == "near-period"


def _two_books(author: str, genre: str, tokens_a: int = 40_000, tokens_b: int = 20_000) -> list[dict]:
    return [
        _book(author, f"{author}.A", tokens_a, genre),
        _book(author, f"{author}.B", tokens_b, genre),
    ]


def test_twelve_cap_per_genre_and_primary_threshold_suffices() -> None:
    rows: list[dict] = []
    for genre, n in (
        ("history", 15),
        ("tafsir", 15),
        ("fiqh", 15),
        ("biography", 15),
        ("poetry_diwan", 5),
        ("maqamat_saj", 3),
        ("prayer_sermon", 2),
        ("hadith_collection", 2),
    ):
        for i in range(n):
            rows.extend(_two_books(f"{genre[:3]}{i:02d}", genre))
    result = select_authors(pd.DataFrame(rows))
    assert not result.relaxed_to_20000
    assert result.genre_counts.get("history") == 12
    assert result.genre_counts.get("tafsir") == 12
    assert result.n_authors >= 60
    assert result.minima_ok
    assert not result.blocked


def test_relaxes_to_20000_when_30000_yields_too_few() -> None:
    rows = []
    for i in range(60):
        rows.append(_book(f"o{i:02d}", f"o{i:02d}.KitabA", 12_000, "other"))
        rows.append(_book(f"o{i:02d}", f"o{i:02d}.KitabB", 10_000, "other"))
    result = select_authors(pd.DataFrame(rows))
    assert result.relaxed_to_20000
    assert result.n_authors == 12  # cap na `other`; reszta to pull coverage (brak)
    assert result.blocked  # < 60 i brak minimow


def test_coverage_pull_ignores_twelve_cap() -> None:
    rows = []
    for i in range(60):
        rows.append(_book(f"x{i:02d}", f"x{i:02d}.KitabA", 40_000, "other"))
        rows.append(_book(f"x{i:02d}", f"x{i:02d}.KitabB", 20_000, "other"))
    # 3 maqama poza capem `other` — regula pokrycia ma ich dociagnac
    for i in range(3):
        rows.append(_book(f"m{i}", f"m{i}.MaqamatA", 40_000, "maqamat_saj"))
        rows.append(_book(f"m{i}", f"m{i}.MaqamatB", 20_000, "maqamat_saj"))
    result = select_authors(pd.DataFrame(rows))
    assert result.genre_counts.get("other") == 12
    assert result.coverage_counts.get("maqamat_saj") == 3
    assert result.coverage_counts.get("maqamat_saj") >= HARD_MINIMA["maqamat_saj"]


def test_coverage_counts_secondary_genre_not_just_primary() -> None:
    """Hariri: duzy inny tom + Maqamat — liczy sie do minimum maqamat."""
    rows: list[dict] = []
    for i in range(60):
        rows.extend(_two_books(f"x{i:02d}", "other"))
    rows.append(_book("hariri", "hariri.Adab", 80_000, "adab_prose"))
    rows.append(_book("hariri", "hariri.Maqamat", 40_000, "maqamat_saj"))
    rows.append(_book("ham", "ham.MaqamatA", 20_000, "maqamat_saj"))
    rows.append(_book("ham", "ham.MaqamatB", 15_000, "maqamat_saj"))
    rows.append(_book("zam", "zam.Tafsir", 80_000, "tafsir"))
    rows.append(_book("zam", "zam.Maqamat", 14_000, "maqamat_saj"))
    result = select_authors(pd.DataFrame(rows))
    assert result.coverage_counts.get("maqamat_saj") >= 3


def test_single_work_exception_admits_anchor_genres_at_15000() -> None:
    ham = aggregate_authors(pd.DataFrame([_book("ham", "ham.Maqamat", 20_751, "maqamat_saj")]))
    assert list(ham["author_id"]) == ["ham"]
    assert ham.iloc[0]["admission_path"] == "single_work_exception"
    assert int(ham.iloc[0]["n_books"]) == 1

    short = aggregate_authors(pd.DataFrame([_book("x", "x.Maqamat", 14_999, "maqamat_saj")]))
    assert short.empty

    tafsir = aggregate_authors(pd.DataFrame([_book("t", "t.Tafsir", 50_000, "tafsir")]))
    assert tafsir.empty


def test_single_work_exception_authors_are_n_books_one() -> None:
    """T-034 PSEUDO-BOOK (03_DATA §11) wymaga n_books>=2 — bez drugiego filtra."""
    rows = [
        _book("ham", "ham.Maqamat", 20_751, "maqamat_saj"),
        _book("poet", "poet.Diwan", 18_000, "poetry_diwan"),
        *_two_books("std", "history"),
    ]
    authors = aggregate_authors(pd.DataFrame(rows))
    exc = authors.loc[authors["admission_path"] == "single_work_exception"]
    assert set(exc["author_id"]) == {"ham", "poet"}
    assert (exc["n_books"] == 1).all()
    assert int(authors.loc[authors["author_id"] == "std", "n_books"].iloc[0]) >= 2
