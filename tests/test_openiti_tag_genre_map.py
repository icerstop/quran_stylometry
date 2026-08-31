"""Kontrakt mapowania tag → genre: zadnego mapped=true bez 3 tytulow."""

from __future__ import annotations

import csv

from src.paths import TAG_GENRE_MAP_PATH


def test_mapped_tags_have_three_to_five_evidence_titles() -> None:
    assert TAG_GENRE_MAP_PATH.is_file(), "najpierw zbuduj openiti_tag_genre_map.csv"
    with TAG_GENRE_MAP_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows, "pusta mapa tagow"
    mapped = [r for r in rows if r["mapped"].strip().lower() == "true"]
    assert mapped, "brak zmapowanych tagow"
    for row in mapped:
        samples = [p.strip() for p in row["evidence_sample"].split("|") if p.strip()]
        assert row["genre"], f"{row['tag']} mapped bez genre"
        assert 3 <= len(samples) <= 5, f"{row['tag']}: {samples!r}"
        assert int(row["n_in_tsv"]) >= 3


def test_unmapped_rows_keep_evidence_trail() -> None:
    with TAG_GENRE_MAP_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    unmapped = [r for r in rows if r["mapped"].strip().lower() != "true"]
    assert unmapped, "odrzut ma zostac w CSV jako slad"
    for row in unmapped:
        assert row["genre"] == ""
        assert row["note"], f"{row['tag']} bez uzasadnienia odrzucenia"
