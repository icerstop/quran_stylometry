"""T-009 — pobranie i sparsowanie EQTB. Testowane bez sieci i bez 7-Zip
(08_REPO.md §3): `fetch`/`extract` sa wstrzykiwane, jak `Fetcher` w
`verify_sources.py`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.data.download_eqtb import (
    EqtbDownloadError,
    canonicalize_columns,
    compute_corpus_stats,
    download_and_parse_eqtb,
    parse_eqtb_csv_bytes,
)

# Kolumny zrodlowe: identyczne z 09_DECISIONS.md §2.1 poza dwoma wyjatkami —
# `constituents_loc` (zamiast `constituent_position`) i brakiem `constituent_node`,
# dokladnie jak w prawdziwym Quranic.csv (potwierdzone w session 2).
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


def synthetic_rows() -> list[dict[str, str]]:
    return [
        # Placeholder: wezel zaleznosciowy klauzuli, identyfikowany przez
        # word_id == '0' (rownowazne location == '_', zweryfikowane na calym
        # pliku Quranic.csv — patrz compute_corpus_stats docstring). rel_label
        # NIE jest tu 'root' celowo: koduje relacje klauzuli, nie sam fakt bycia
        # placeholderem.
        _row(
            tid="0",
            sentence_id="1",
            location="_",
            chapter_id="_",
            verse_id="_",
            word_id="0",
            rel_label="Pred",
        ),
        # Slowo "1:1:1" ma DWA segmenty morfologiczne (ten sam word_id, dwa tid) —
        # zeby test odroznial n_segments (wiersze) od n_tokens (distinct slowa).
        _row(
            tid="1",
            sentence_id="1",
            location="(1:1:1:1)",
            chapter_id="1",
            verse_id="1",
            word_id="1",
            imlaai_token="بِ",
            pos="P",
        ),
        _row(
            tid="2",
            sentence_id="1",
            location="(1:1:1:2)",
            chapter_id="1",
            verse_id="1",
            word_id="1",
            imlaai_token="سْمِ",
            pos="N",
        ),
        _row(
            tid="3",
            sentence_id="1",
            location="(1:1:2:1)",
            chapter_id="1",
            verse_id="1",
            word_id="2",
            imlaai_token="اللَّهِ",
            pos="PN",
        ),
        # Sura 2, werset 5 — verse_id="5" tutaj ROWNA SIE werset_id="1" z sury 1
        # w liczeniu naiwnym (bez chapter_id); test pilnuje, ze n_tokens liczy
        # (chapter_id, verse_id, word_id), nie samo (verse_id, word_id).
        _row(
            tid="4",
            sentence_id="2",
            location="(2:1:1:1)",
            chapter_id="2",
            verse_id="1",
            word_id="1",
            imlaai_token="ذَلِكَ",
            pos="DEM",
        ),
    ]


def synthetic_csv_bytes(rows: list[dict[str, str]]) -> bytes:
    header = "\t".join(SOURCE_COLUMNS)
    lines = [header] + ["\t".join(row[c] for c in SOURCE_COLUMNS) for row in rows]
    text = "\n".join(lines) + "\n"
    return b"\xff\xfe" + text.encode("utf-16-le")


# --------------------------------------------------------------------------
# parse_eqtb_csv_bytes
# --------------------------------------------------------------------------


def test_parse_eqtb_csv_bytes_reads_utf16_tab_file() -> None:
    df = parse_eqtb_csv_bytes(synthetic_csv_bytes(synthetic_rows()))
    assert list(df.columns) == SOURCE_COLUMNS
    assert len(df) == 5
    assert df.iloc[1]["imlaai_token"] == "بِ"


# --------------------------------------------------------------------------
# canonicalize_columns
# --------------------------------------------------------------------------


def test_canonicalize_columns_applies_confirmed_rename() -> None:
    df = parse_eqtb_csv_bytes(synthetic_csv_bytes(synthetic_rows()))
    canonical = canonicalize_columns(
        df, expected_columns=EXPECTED_COLUMNS, rename=RENAME, unresolved=UNRESOLVED
    )
    assert list(canonical.columns) == EXPECTED_COLUMNS
    assert "constituents_loc" not in canonical.columns
    assert canonical["constituent_position"].tolist() == df["constituents_loc"].tolist()


def test_canonicalize_columns_leaves_unresolved_column_null() -> None:
    """09_DECISIONS.md §2.1: constituent_node zostaje nullable/unmapped, nie zgadywane."""
    df = parse_eqtb_csv_bytes(synthetic_csv_bytes(synthetic_rows()))
    canonical = canonicalize_columns(
        df, expected_columns=EXPECTED_COLUMNS, rename=RENAME, unresolved=UNRESOLVED
    )
    assert canonical["constituent_node"].isna().all()


def test_canonicalize_columns_fails_loudly_on_unexplained_missing_column() -> None:
    """Kolumna brakujaca bez znanego mapowania/unresolved = blad, nie domysl."""
    df = parse_eqtb_csv_bytes(synthetic_csv_bytes(synthetic_rows()))
    with pytest.raises(EqtbDownloadError):
        canonicalize_columns(
            df,
            expected_columns=[*EXPECTED_COLUMNS, "totally_new_field"],
            rename=RENAME,
            unresolved=[],
        )


# --------------------------------------------------------------------------
# compute_corpus_stats
# --------------------------------------------------------------------------


def test_compute_corpus_stats_distinguishes_segments_from_orthographic_words() -> None:
    """n_segments = wiersze (morfemy); n_tokens = distinct slowa ortograficzne
    (chapter_id, verse_id, word_id) — token_unit z docs/09_DECISIONS.md §6.
    Dwa wiersze w danych syntetycznych dziela jeden word_id (dwa segmenty
    jednego slowa), wiec n_segments > n_tokens tak jak w prawdziwym korpusie."""
    df = parse_eqtb_csv_bytes(synthetic_csv_bytes(synthetic_rows()))
    canonical = canonicalize_columns(
        df, expected_columns=EXPECTED_COLUMNS, rename=RENAME, unresolved=UNRESOLVED
    )
    stats = compute_corpus_stats(canonical)

    assert stats["n_raw_rows"] == 5
    assert stats["n_root_placeholder_rows"] == 1
    assert stats["n_segments"] == 4
    assert stats["n_tokens"] == 3
    assert stats["n_surahs"] == 2
    assert stats["n_verses"] == 2


def test_compute_corpus_stats_requires_chapter_id_not_just_verse_id() -> None:
    """verse_id resetuje sie co sure (max 286 w realnych danych) — samo
    (verse_id, word_id) zderzalo by werset 1 sury 1 z wersetem 1 sury 2."""
    df = parse_eqtb_csv_bytes(synthetic_csv_bytes(synthetic_rows()))
    canonical = canonicalize_columns(
        df, expected_columns=EXPECTED_COLUMNS, rename=RENAME, unresolved=UNRESOLVED
    )
    real = canonical.loc[canonical["word_id"].astype(str).str.strip() != "0"]
    naive_pairs = real[["verse_id", "word_id"]].drop_duplicates().shape[0]
    correct_pairs = real[["chapter_id", "verse_id", "word_id"]].drop_duplicates().shape[0]

    assert naive_pairs == 2  # (verse=1, word=1) z sury 1 i sury 2 zderzaja sie
    assert correct_pairs == 3
    assert compute_corpus_stats(canonical)["n_tokens"] == correct_pairs


# --------------------------------------------------------------------------
# download_and_parse_eqtb — orkiestracja z fake fetch/extract
# --------------------------------------------------------------------------


def test_download_and_parse_eqtb_writes_cache_and_computes_stats(tmp_path: Path) -> None:
    csv_bytes = synthetic_csv_bytes(synthetic_rows())
    calls = {"fetch": 0, "extract": 0}

    def fake_fetch() -> bytes:
        calls["fetch"] += 1
        return b"fake-rar-bytes"

    def fake_extract(archive_bytes: bytes) -> bytes:
        calls["extract"] += 1
        assert archive_bytes == b"fake-rar-bytes"
        return csv_bytes

    result = download_and_parse_eqtb(
        fetch=fake_fetch,
        extract=fake_extract,
        raw_archive_path=tmp_path / "raw" / "Quranic.rar",
        raw_csv_path=tmp_path / "raw" / "Quranic.csv",
        tokens_path=tmp_path / "interim" / "eqtb_tokens.parquet",
    )

    assert calls == {"fetch": 1, "extract": 1}
    assert result.from_cache is False
    assert result.tokens_path.exists()
    assert result.raw_archive_path.read_bytes() == b"fake-rar-bytes"
    assert result.stats["n_segments"] == 4
    assert result.stats["n_tokens"] == 3
    assert result.stats["n_surahs"] == 2
    assert result.stats["unresolved_columns"] == ["constituent_node"]
    assert result.stats["column_rename_applied"] == {"constituents_loc": "constituent_position"}
    assert result.stats["pipeline_input_column"] == "imlaai_token"

    saved = pd.read_parquet(result.tokens_path)
    assert "constituent_position" in saved.columns
    assert "constituent_node" in saved.columns


def test_download_and_parse_eqtb_uses_cache_and_skips_fetch(tmp_path: Path) -> None:
    csv_path = tmp_path / "raw" / "Quranic.csv"
    csv_path.parent.mkdir(parents=True)
    csv_path.write_bytes(synthetic_csv_bytes(synthetic_rows()))

    def fail_fetch() -> bytes:
        raise AssertionError("nie powinno pobierac, bo cache juz istnieje")

    def fail_extract(archive_bytes: bytes) -> bytes:
        raise AssertionError("nie powinno rozpakowywac, bo cache juz istnieje")

    result = download_and_parse_eqtb(
        fetch=fail_fetch,
        extract=fail_extract,
        raw_archive_path=tmp_path / "raw" / "Quranic.rar",
        raw_csv_path=csv_path,
        tokens_path=tmp_path / "interim" / "eqtb_tokens.parquet",
    )
    assert result.from_cache is True
    assert result.stats["n_tokens"] == 3
    assert result.stats["n_segments"] == 4


def test_download_and_parse_eqtb_force_redownloads_even_with_cache(tmp_path: Path) -> None:
    csv_path = tmp_path / "raw" / "Quranic.csv"
    csv_path.parent.mkdir(parents=True)
    csv_path.write_bytes(b"stale cache that should be overwritten")

    calls = {"fetch": 0, "extract": 0}

    def fake_fetch() -> bytes:
        calls["fetch"] += 1
        return b"fresh-rar-bytes"

    def fake_extract(archive_bytes: bytes) -> bytes:
        calls["extract"] += 1
        return synthetic_csv_bytes(synthetic_rows())

    result = download_and_parse_eqtb(
        fetch=fake_fetch,
        extract=fake_extract,
        force=True,
        raw_archive_path=tmp_path / "raw" / "Quranic.rar",
        raw_csv_path=csv_path,
        tokens_path=tmp_path / "interim" / "eqtb_tokens.parquet",
    )
    assert calls == {"fetch": 1, "extract": 1}
    assert result.from_cache is False
    assert result.stats["n_tokens"] == 3
    assert result.stats["n_segments"] == 4
