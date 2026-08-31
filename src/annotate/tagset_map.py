"""Mapowanie tagsetu CAMeL (calima-msa-r13) ↔ EQTB/QAC (T-014).

T-010 odlozylo to mapowanie tutaj: referencja to kolumny EQTB, nie plik QAC
(`results/qac_fallback.json`, status=fallback_active). Tabela zrodlowa:
`data/reference/eqtb_camel_pos_map.csv`.

Dwie warstwy:
- fine: CAMeL POS → jeden tag EQTB (albo brak, wtedy mapped=false);
- coarse: 9 kubełkow wspolnych, zeby accuracy nie karala za ziarnistosc QAC
  (20+ partykul), ktorej CALIMA nie ma.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from src.paths import TAGSET_MAP_PATH

COARSE_TAGS: tuple[str, ...] = (
    "NOUN",
    "ADJ",
    "VERB",
    "PRON",
    "PREP",
    "CONJ",
    "DET",
    "ADV",
    "PART",
)

# Inwentarz EQTB (45 tagow, results/_eqtb_pos_probe.json / T-009 parquet).
# Grupowanie jest decyzja T-014, nie zgadywaniem brakujacego pola zrodla.
EQTB_TO_COARSE: dict[str, str] = {
    "N": "NOUN",
    "PN": "NOUN",
    "ADJ": "ADJ",
    "V": "VERB",
    "PRON": "PRON",
    "REL": "PRON",
    "DEM": "PRON",
    "P": "PREP",
    "CONJ": "CONJ",
    "SUB": "CONJ",
    "REM": "CONJ",
    "DET": "DET",
    "T": "ADV",
    "LOC": "ADV",
    "ACC": "PART",
    "AMD": "PART",
    "ANS": "PART",
    "AVR": "PART",
    "CAUS": "PART",
    "CERT": "PART",
    "CIRC": "PART",
    "COM": "PART",
    "COND": "PART",
    "EMPH": "PART",
    "EQ": "PART",
    "EXH": "PART",
    "EXL": "PART",
    "EXP": "PART",
    "FUT": "PART",
    "IMPN": "PART",
    "IMPV": "PART",
    "INC": "PART",
    "INL": "PART",
    "INT": "PART",
    "INTG": "PART",
    "NEG": "PART",
    "PREV": "PART",
    "PRO": "PART",
    "PRP": "PART",
    "RES": "PART",
    "RET": "PART",
    "RSLT": "PART",
    "SUP": "PART",
    "SUR": "PART",
    "VOC": "PART",
}

UNKNOWN_COARSE = "PART"


@dataclass(frozen=True)
class CamelPosMapping:
    camel_pos: str
    eqtb_pos: str | None
    coarse: str
    mapped: bool
    note: str


@lru_cache(maxsize=1)
def load_camel_pos_map(path: Path | None = None) -> dict[str, CamelPosMapping]:
    csv_path = path or TAGSET_MAP_PATH
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    out: dict[str, CamelPosMapping] = {}
    for row in rows:
        camel = row["camel_pos"].strip()
        eqtb = row["eqtb_pos"].strip() or None
        mapped = row["mapped"].strip().lower() == "true"
        out[camel] = CamelPosMapping(
            camel_pos=camel,
            eqtb_pos=eqtb,
            coarse=row["coarse"].strip() or UNKNOWN_COARSE,
            mapped=mapped,
            note=row.get("note", "").strip(),
        )
    return out


def camel_to_eqtb(camel_pos: str, *, path: Path | None = None) -> str | None:
    rec = load_camel_pos_map(path).get(camel_pos.strip().lower())
    if rec is None or not rec.mapped:
        return None
    return rec.eqtb_pos


def camel_to_coarse(camel_pos: str, *, path: Path | None = None) -> str:
    rec = load_camel_pos_map(path).get(camel_pos.strip().lower())
    if rec is None:
        return UNKNOWN_COARSE
    return rec.coarse


def eqtb_to_coarse(eqtb_pos: str) -> str:
    return EQTB_TO_COARSE.get(eqtb_pos.strip().upper(), UNKNOWN_COARSE)
