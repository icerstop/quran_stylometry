"""Regresja T-016: Q33:56 w KashfWaBayan musi byc exact-hit po naprawie.

Audyt 2×100, nonmatches[65]:
  book 0427AbuIshaqThaclabi.KashfWaBayan.Shamela0023578-ara1
  window = يصلون علي النبي يا ايها الذين امنوا
To 7 kolejnych tokenow = Q33:56 (...يصلون على النبي يا أيها الذين آمنوا...).
"""

from __future__ import annotations

from src.config import QuotesCfg
from src.data.detect_quran_quotes import (
    concat_key,
    scan_book,
    token_concat_needles,
    token_ngrams,
)
from src.data.normalize_arabic import normalize

# Strumien Koranu jak po grupowaniu EQTB word_id (przed ءا→ا): Q33:56.
_Q33_56_EQTB_WORDS = [
    "ان",
    "الله",
    "ومليكته",
    "يصلون",
    "علي",
    "النبي",
    "يايها",
    "الذين",
    "ءامنوا",
    "صلوا",
    "عليه",
    "وسلموا",
    "تسليما",
]

# CTRL (ctrl_capped, start=24371) — te same 7 tokenow co w audycie, bez ukrytych znakow.
_CTRL_WINDOW = ["يصلون", "علي", "النبي", "يا", "ايها", "الذين", "امنوا"]
_CTRL_CONTEXT = [
    "عز",
    "وجل",
    "ان",
    "الله",
    "وملايكته",
    *_CTRL_WINDOW,
    "صلوا",
    "عليه",
    "pad1",
    "pad2",
    "pad3",
    "والصلاه",
]


def _quran_index() -> tuple[list[str], set[tuple[str, ...]], set[str]]:
    quran = [normalize(tok, "strict") for tok in _Q33_56_EQTB_WORDS]
    n = QuotesCfg().quote_ngram_n
    return quran, set(token_ngrams(quran, n)), token_concat_needles(quran, n)


def test_hamza_alif_is_the_same_normalizer_on_both_sides() -> None:
    """H1: ءامنوا (EQTB) i امنوا (CTRL) po strict daja ten sam token."""
    eqtb = normalize("ءامنوا", "strict")
    ctrl = normalize("امنوا", "strict")
    madda = normalize("آمنوا", "strict")
    assert eqtb == ctrl == madda == "امنوا"
    cps_ctrl = [hex(ord(ch)) for ch in _CTRL_WINDOW[-1]]
    cps_norm = [hex(ord(ch)) for ch in eqtb]
    assert cps_ctrl == cps_norm


def test_quran_index_has_mid_verse_7gram_at_stride_one() -> None:
    """H2: indeks ma krok 1, fragment siedzi w srodku Q33:56, nie na granicy wersetu."""
    quran, exact, _needles = _quran_index()
    assert quran[3:10][0] == "يصلون"
    mid = tuple(quran[3:10])
    assert mid in exact
    # To NIE jest ten sam 7-gram co CTRL (يايها vs يا+ايها) — stride dziala.
    assert tuple(_CTRL_WINDOW) not in exact


def test_ctrl_window_has_no_hidden_codepoint_artifact() -> None:
    """H3: okno audytu = czysty UTF-8, identyczny z plikiem zrodlowym po split()."""
    joined = " ".join(_CTRL_WINDOW)
    assert joined.encode("utf-8").hex() == (
        "d98ad8b5d984d988d98620d8b9d984d98a20d8a7d984d986d8a8d98a20"
        "d98ad8a720d8a7d98ad987d8a720d8a7d984d8b0d98ad98620d8a7d985d986d988d8a7"
    )
    assert [normalize(t, "strict") for t in _CTRL_WINDOW] == _CTRL_WINDOW


def test_vocative_glue_is_why_tuple_exact_misses() -> None:
    """EQTB word_id skleja ي+أيها → يايها; OpenITI ma يا ايها (plus alif)."""
    quran, exact, needles = _quran_index()
    assert quran[6] == "يايها"
    assert _CTRL_WINDOW[3:5] == ["يا", "ايها"]
    assert tuple(_CTRL_WINDOW) not in exact
    folded_quran = concat_key(quran[3:10])
    folded_ctrl = concat_key(_CTRL_WINDOW + ["صلوا"])
    assert folded_quran == folded_ctrl
    assert folded_quran in needles


def test_q3356_thaclabi_seven_gram_is_detected() -> None:
    """Ten fragment MUSI byc wykryty — DoD regresji po audycie 2×100."""
    quran, exact, needles = _quran_index()
    vocab = set(quran)
    result = scan_book(
        _CTRL_CONTEXT,
        exact=exact,
        fuzzy=None,
        vocab=vocab,
        cfg=QuotesCfg(),
        concat_needles=needles,
    )
    assert result["n_concat_hits"] >= 1 or result["n_exact_hits"] >= 1
    cleaned = set(result["cleaned"])
    for tok in _CTRL_WINDOW:
        assert tok not in cleaned, f"{tok!r} mial zostac wyciety jako cytat Q33:56"
    assert "والصلاه" in cleaned
