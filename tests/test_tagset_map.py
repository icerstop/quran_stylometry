"""Mapowanie CAMeL ↔ EQTB jest kompletne i bez Farasy."""

from __future__ import annotations

import csv

from src.annotate.tagset_map import (
    EQTB_TO_COARSE,
    TAGSET_MAP_PATH,
    camel_to_coarse,
    camel_to_eqtb,
    eqtb_to_coarse,
    load_camel_pos_map,
)


def test_csv_exists_and_covers_calima_inventory() -> None:
    mapping = load_camel_pos_map()
    assert TAGSET_MAP_PATH.is_file()
    required = {
        "noun",
        "noun_prop",
        "verb",
        "prep",
        "conj",
        "part_det",
        "pron",
        "adj",
        "part",
    }
    assert required <= set(mapping)
    with TAGSET_MAP_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert {r["camel_pos"] for r in rows} == set(mapping)


def test_noun_and_prep_map_to_eqtb() -> None:
    assert camel_to_eqtb("noun") == "N"
    assert camel_to_eqtb("NOUN") == "N"
    assert camel_to_eqtb("prep") == "P"
    assert camel_to_eqtb("part") is None
    assert camel_to_coarse("part") == "PART"
    assert camel_to_coarse("unknown_tag") == "PART"


def test_all_observed_eqtb_pos_have_coarse_bucket() -> None:
    observed = {
        "ACC",
        "ADJ",
        "AMD",
        "ANS",
        "AVR",
        "CAUS",
        "CERT",
        "CIRC",
        "COM",
        "COND",
        "CONJ",
        "DEM",
        "DET",
        "EMPH",
        "EQ",
        "EXH",
        "EXL",
        "EXP",
        "FUT",
        "IMPN",
        "IMPV",
        "INC",
        "INL",
        "INT",
        "INTG",
        "LOC",
        "N",
        "NEG",
        "P",
        "PN",
        "PREV",
        "PRO",
        "PRON",
        "PRP",
        "REL",
        "REM",
        "RES",
        "RET",
        "RSLT",
        "SUB",
        "SUP",
        "SUR",
        "T",
        "V",
        "VOC",
    }
    assert observed == set(EQTB_TO_COARSE)
    assert eqtb_to_coarse("N") == "NOUN"
    assert eqtb_to_coarse("T") == "ADV"
    assert eqtb_to_coarse("ZZZ") == "PART"
