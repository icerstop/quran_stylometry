"""Regresja: `n_tokens` z T-009 ma odpowiadac ``token_unit: orthographic_word``
(docs/09_DECISIONS.md §6), nie liczbie segmentow morfologicznych.

Pomylka wykryta 2026-08-30: `compute_corpus_stats` liczyl `n_tokens` jako liczbe
wierszy po odfiltrowaniu placeholderow (czyli w istocie `n_segments`), przez co
wynik (128219) nie mial nic wspolnego z referencyjna liczba QAC (77429). Ten
test pilnuje, zeby to nie wrocilo cicho przy nastepnej zmianie parsera —
dziala na syntetycznych danych (bez sieci, bez 7-Zip, 08_REPO.md §3).

Referencja QAC = **77429**, nie powszechnie cytowane w zrodlach trzeciorzednych
"77430" (Wikipedia, blogi) — zweryfikowane wobec zrodla pierwotnego
(`corpus.quran.com/java/example/tokencountexample.jsp`, wlasna tabela
`Chapter.getTokenCount()` QAC dla 114 sur, ktora sama sumuje sie do 77429).
Dowod chapter-po-chapter (0/114 roznic): `scripts/probe_word_count_discrepancy.py`,
`results/eqtb_vs_qac_per_surah.csv`, `SOURCES.md` §4, `DEVIATIONS.md` D-06.
"""

from __future__ import annotations

from src.data.download_eqtb import canonicalize_columns, compute_corpus_stats, parse_eqtb_csv_bytes

QAC_REFERENCE_N_WORDS = 77_429
TOLERANCE = 0.01  # +/-1%: edycje/wersje moga sie nieznacznie roznic (AGENTS.md zasada 8)

SOURCE_COLUMNS = [
    "tid",
    "sentence_id",
    "verse_id",
    "word_id",
    "tok_id",
    "location",
    "chapter_id",
    "uthmani_token",
    "imlaai_token",
    "uthmani_unicode",
    "imlaai_unicode",
    "phonetic",
    "trans",
    "pos",
    "pos_ar",
    "features",
    "segment",
    "lemma",
    "lemma_ar",
    "root",
    "root_ar",
    "verb_form",
    "prefix",
    "suffix",
    "verb_aspect",
    "nominal_state",
    "verb_mood",
    "nominal_case",
    "derived_nouns",
    "verb_voice",
    "person",
    "gender",
    "number",
    "special_group",
    "rel_label",
    "rel_label_ar",
    "ref_token_id",
    "is_constituent",
    "constituents_loc",
    "constituents",
    "constituent_label",
]
EXPECTED_COLUMNS = [
    c if c != "constituents_loc" else "constituent_position" for c in SOURCE_COLUMNS
]
EXPECTED_COLUMNS.insert(EXPECTED_COLUMNS.index("constituent_position"), "constituent_node")
RENAME = {"constituents_loc": "constituent_position"}
UNRESOLVED = ["constituent_node"]


def _row(**overrides: str) -> dict[str, str]:
    base = dict.fromkeys(SOURCE_COLUMNS, "_")
    base.update(overrides)
    return base


def synthetic_csv_bytes(rows: list[dict[str, str]]) -> bytes:
    header = "\t".join(SOURCE_COLUMNS)
    lines = [header] + ["\t".join(row[c] for c in SOURCE_COLUMNS) for row in rows]
    text = "\n".join(lines) + "\n"
    return b"\xff\xfe" + text.encode("utf-16-le")


def three_segment_word() -> list[dict[str, str]]:
    """Jedno slowo ortograficzne rozbite na TRZY segmenty (proklityka + temat +
    sufiks) — jesli ktos znowu policzy `n_tokens` jako liczbe wierszy, ten test
    zobaczy 3 tokeny miast 1."""
    return [
        _row(tid="0", sentence_id="1", location="_", chapter_id="_", verse_id="_", word_id="0"),
        _row(
            tid="1",
            sentence_id="1",
            location="(1:1:1:1)",
            chapter_id="1",
            verse_id="1",
            word_id="1",
            imlaai_token="وَ",
        ),
        _row(
            tid="2",
            sentence_id="1",
            location="(1:1:1:2)",
            chapter_id="1",
            verse_id="1",
            word_id="1",
            imlaai_token="كِتَاب",
        ),
        _row(
            tid="3",
            sentence_id="1",
            location="(1:1:1:3)",
            chapter_id="1",
            verse_id="1",
            word_id="1",
            imlaai_token="هُ",
        ),
    ]


def _canonical(rows: list[dict[str, str]]):
    df = parse_eqtb_csv_bytes(synthetic_csv_bytes(rows))
    return canonicalize_columns(
        df, expected_columns=EXPECTED_COLUMNS, rename=RENAME, unresolved=UNRESOLVED
    )


def test_n_tokens_counts_orthographic_words_not_morphological_segments() -> None:
    """token_unit: orthographic_word (docs/09_DECISIONS.md §6) — jedno slowo,
    trzy segmenty w zrodle, `n_tokens` musi zostac 1, `n_segments` musi zostac 3."""
    stats = compute_corpus_stats(_canonical(three_segment_word()))
    assert stats["n_tokens"] == 1
    assert stats["n_segments"] == 3


def test_n_tokens_never_equals_row_count_when_words_are_multi_segment() -> None:
    """Straznik regresji: gdyby ktos znowu podstawil `len(real_tokens)` pod
    `n_tokens`, ten test wywrocilby sie natychmiast (3 != 1)."""
    canonical = _canonical(three_segment_word())
    stats = compute_corpus_stats(canonical)
    n_rows_after_filter = (canonical["word_id"].astype(str).str.strip() != "0").sum()
    assert stats["n_tokens"] != n_rows_after_filter


def test_real_eqtb_parquet_word_count_is_within_one_percent_of_qac_reference() -> None:
    """Liczba distinct slow ortograficznych w PRAWDZIWYM, juz sparsowanym
    `data/interim/eqtb_tokens.parquet` (T-009) ma byc w rozsądnym zakresie
    (+/-1%) wokol referencyjnej wartosci QAC 77429 — tolerancja zostaje jako
    margines bezpieczenstwa na przyszle edycje/wersje EQTB, mimo ze aktualny
    plik zgadza sie z referencja DOKLADNIE (diff=0, patrz test nizej). Nigdy
    nie powinno wypadac blisko ~128k (liczba segmentow, nie slow — dokladnie
    ta pomylka, ktora ten plik ma wykrywac). Pominiety, jesli T-009 jeszcze
    nie bylo uruchomione lokalnie.
    """
    import pytest

    from src.data.download_eqtb import INTERIM_TOKENS_PATH

    if not INTERIM_TOKENS_PATH.exists():
        pytest.skip("data/interim/eqtb_tokens.parquet nie istnieje — uruchom `make download-eqtb`")

    import pandas as pd

    df = pd.read_parquet(INTERIM_TOKENS_PATH)
    stats = compute_corpus_stats(df)

    lower = QAC_REFERENCE_N_WORDS * (1 - TOLERANCE)
    upper = QAC_REFERENCE_N_WORDS * (1 + TOLERANCE)
    assert lower <= stats["n_tokens"] <= upper, (
        f"n_tokens={stats['n_tokens']} poza +/-1% wokol referencji QAC "
        f"{QAC_REFERENCE_N_WORDS} — patrz DEVIATIONS.md D-06."
    )


def test_real_eqtb_parquet_matches_qac_java_api_exactly_per_chapter() -> None:
    """Dowod z primary source: `Chapter.getTokenCount()` (QAC Java API,
    corpus.quran.com/java/example/tokencountexample.jsp) zgadza sie z EQTB
    dla WSZYSTKICH 114 sur, bez wyjatku — nie tylko w tolerancji +/-1%.
    Pelna tabela referencyjna: `scripts/probe_word_count_discrepancy.py`.
    Pominiety, jesli T-009 jeszcze nie bylo uruchomione lokalnie.
    """
    import pytest

    from src.data.download_eqtb import INTERIM_TOKENS_PATH

    if not INTERIM_TOKENS_PATH.exists():
        pytest.skip("data/interim/eqtb_tokens.parquet nie istnieje — uruchom `make download-eqtb`")

    import pandas as pd

    from src.data.download_qac import QAC_JAVA_API_TOKEN_COUNTS

    df = pd.read_parquet(INTERIM_TOKENS_PATH)
    real = df.loc[df["word_id"].astype(str).str.strip() != "0"].copy()
    real["chapter_id_int"] = real["chapter_id"].astype(int)
    real["verse_id_int"] = real["verse_id"].astype(int)
    real["word_id_int"] = real["word_id"].astype(int)
    per_chapter = real.groupby("chapter_id_int").apply(
        lambda g: g[["verse_id_int", "word_id_int"]].drop_duplicates().shape[0],
        include_groups=False,
    )

    assert dict(per_chapter) == QAC_JAVA_API_TOKEN_COUNTS
    assert sum(per_chapter) == QAC_REFERENCE_N_WORDS == 77_429
