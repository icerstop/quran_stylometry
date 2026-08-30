"""T-010 — formalizacja fallbacku QAC, BEZ pobierania (docs/09_DECISIONS.md §2.2).

`docs/07_TASKS.md` opisuje T-010 jako pobranie pliku morfologii QAC. Wykonanie
tego wymaga formularza z adresem e-mail na `corpus.quran.com/download/` —
koliduje z AGENTS.md zasada 9 ("bez rejestracji") i z odtwarzalnoscia T-051.

Decyzja (2026-08-30): T-010 konczy sie bez zadnego pobierania. Referencja dla
ewaluacji taggera w T-014 to kolumny morfologiczne EQTB
(`data/interim/eqtb_tokens.parquet`, T-009), nie zewnetrzny plik QAC.

Ten modul:

* NIE woła `corpus.quran.com/download/` i NIE zapisuje nic w `data/raw/qac/`;
* zapisuje `results/qac_fallback.json` — maszynowy slad decyzji;
* trzyma tabele `Chapter.getTokenCount()` z Java API QAC (zrodlo pierwotne,
  strona publiczna, bez formularza) — uzywana wylacznie do weryfikacji
  `n_tokens`, nigdy jako dane wejsciowe pipeline'u.

Mapowanie tagsetow (tagger produkcyjny <-> tagset EQTB, nie QAC) przesuwa sie
do T-014, gdzie bedzie mialo konkretny kontekst uzycia.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.paths import DATA_INTERIM_DIR, DATA_RAW_DIR, RESULTS_DIR
from src.utils.io import write_json
from src.utils.logging import get_logger
from src.utils.provenance import utc_now_iso

LOGGER = get_logger(__name__)

EQTB_TOKENS_PATH: Path = DATA_INTERIM_DIR / "eqtb_tokens.parquet"
QAC_RAW_DIR: Path = DATA_RAW_DIR / "qac"
QAC_FALLBACK_PATH: Path = RESULTS_DIR / "qac_fallback.json"

# Kolumny EQTB uzywane jako referencja morfologiczna w T-014 (09_DECISIONS §2.2).
EQTB_MORPH_REFERENCE_COLUMNS: tuple[str, ...] = (
    "pos",
    "pos_ar",
    "features",
    "lemma",
    "lemma_ar",
    "root",
    "root_ar",
    "segment",
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
)

# Zrodlo pierwotne, nie wtorne: "Program Output" z
# https://corpus.quran.com/java/example/tokencountexample.jsp (pobrane 2026-08-30).
# `Chapter.getTokenCount()` — "Each orthographic token is whitespace delimited
# Arabic text within a verse." Ta sama definicja co token_unit: orthographic_word
# (docs/09_DECISIONS.md §6). Suma = 77429, nie powszechnie cytowane 77430.
QAC_JAVA_API_TOKEN_COUNTS: dict[int, int] = {
    1: 29,
    2: 6116,
    3: 3481,
    4: 3747,
    5: 2804,
    6: 3050,
    7: 3320,
    8: 1233,
    9: 2498,
    10: 1833,
    11: 1917,
    12: 1777,
    13: 853,
    14: 830,
    15: 655,
    16: 1844,
    17: 1556,
    18: 1579,
    19: 961,
    20: 1335,
    21: 1169,
    22: 1274,
    23: 1050,
    24: 1316,
    25: 893,
    26: 1318,
    27: 1151,
    28: 1430,
    29: 976,
    30: 817,
    31: 546,
    32: 372,
    33: 1287,
    34: 883,
    35: 775,
    36: 725,
    37: 860,
    38: 733,
    39: 1172,
    40: 1219,
    41: 794,
    42: 860,
    43: 830,
    44: 346,
    45: 488,
    46: 643,
    47: 539,
    48: 560,
    49: 347,
    50: 373,
    51: 360,
    52: 312,
    53: 360,
    54: 342,
    55: 351,
    56: 379,
    57: 574,
    58: 472,
    59: 445,
    60: 348,
    61: 221,
    62: 175,
    63: 180,
    64: 241,
    65: 287,
    66: 249,
    67: 333,
    68: 300,
    69: 258,
    70: 217,
    71: 226,
    72: 285,
    73: 199,
    74: 255,
    75: 164,
    76: 243,
    77: 181,
    78: 173,
    79: 179,
    80: 133,
    81: 104,
    82: 80,
    83: 169,
    84: 107,
    85: 109,
    86: 61,
    87: 72,
    88: 92,
    89: 137,
    90: 82,
    91: 54,
    92: 71,
    93: 40,
    94: 27,
    95: 34,
    96: 72,
    97: 30,
    98: 94,
    99: 36,
    100: 40,
    101: 36,
    102: 28,
    103: 14,
    104: 33,
    105: 23,
    106: 17,
    107: 25,
    108: 10,
    109: 26,
    110: 19,
    111: 23,
    112: 15,
    113: 23,
    114: 20,
}

QAC_JAVA_API_N_TOKENS: int = sum(QAC_JAVA_API_TOKEN_COUNTS.values())
QAC_JAVA_API_SOURCE = "https://corpus.quran.com/java/example/tokencountexample.jsp"


class QacDownloadForbiddenError(RuntimeError):
    """Proba pobrania pliku QAC — T-010 tego nie robi."""


@dataclass(frozen=True)
class QacFallbackResult:
    artifact_path: Path
    payload: dict[str, Any]


def formalize_qac_fallback(
    *,
    eqtb_tokens_path: Path = EQTB_TOKENS_PATH,
    artifact_path: Path = QAC_FALLBACK_PATH,
) -> QacFallbackResult:
    """Zapisuje sformalizowany fallback. Zero sieci, zero `data/raw/qac/`."""
    if QAC_RAW_DIR.exists() and any(QAC_RAW_DIR.iterdir()):
        raise QacDownloadForbiddenError(
            f"{QAC_RAW_DIR} nie powinno istniec — T-010 nie pobiera QAC. "
            "Usun katalog i uruchom ponownie."
        )

    eqtb_ready = eqtb_tokens_path.exists()
    payload: dict[str, Any] = {
        "task": "T-010",
        "status": "fallback_active",
        "checked_at": utc_now_iso(),
        "decision_ref": "docs/09_DECISIONS.md §2.2",
        "qac_downloaded": False,
        "download_attempted": False,
        "reference_corpus": "eqtb",
        "reference_path": "data/interim/eqtb_tokens.parquet",
        "reference_available": eqtb_ready,
        "eqtb_morph_columns": list(EQTB_MORPH_REFERENCE_COLUMNS),
        "qac_download_url_unused": "https://corpus.quran.com/download/",
        "reason": (
            "Formularz e-mail na corpus.quran.com/download/ koliduje z "
            "AGENTS.md zasada 9 (bez rejestracji) i z odtwarzalnoscia T-051. "
            "09_DECISIONS.md §2.2 przewiduje ten fallback jako dozwolony, "
            "nie jako blocker."
        ),
        "deferred_to_t014": ("Mapowanie tagsetu: tagger produkcyjny <-> tagset EQTB (nie QAC)."),
        "qac_java_api_n_tokens": QAC_JAVA_API_N_TOKENS,
        "qac_java_api_source": QAC_JAVA_API_SOURCE,
        "qac_java_api_used_as": (
            "wylacznie weryfikacja n_tokens (orthographic_word), nigdy jako "
            "dane wejsciowe pipeline'u ani jako referencja taggera"
        ),
    }
    write_json(artifact_path, payload)
    LOGGER.info(
        "sformalizowano fallback QAC",
        extra={"artifact": str(artifact_path), "eqtb_ready": eqtb_ready},
    )
    return QacFallbackResult(artifact_path=artifact_path, payload=payload)
