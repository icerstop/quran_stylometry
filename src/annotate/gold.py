"""Gold na poziomie slowa ortograficznego z EQTB (T-014, token_unit).

Jednostka ewaluacji = distinct (chapter_id, verse_id, word_id) = 77429,
nie wiersz tabeli (segment morfologiczny). Placeholder ``word_id == 0``
odrzucany tak samo jak w ``compute_corpus_stats`` (T-009).

Lemat STEM: ``lemma_ar`` jesli niepuste, w przeciwnym razie Buckwalter
``lemma`` przez standardowa tabele BW→Unicode (to kodowanie, nie zgadywanie
pola zrodla).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from src.data.normalize_arabic import normalize

# Standard Buckwalter (QAC/EQTB). Hamza/alif warianty sa potem zjadane przez
# normalize(strict) — porownanie lematow idzie po tej samej sciezce co CTRL.
_BW2AR = str.maketrans(
    {
        "'": "ء",
        "|": "آ",
        ">": "أ",
        "&": "ؤ",
        "<": "إ",
        "}": "ئ",
        "{": "ٱ",
        "A": "ا",
        "b": "ب",
        "p": "ة",
        "t": "ت",
        "v": "ث",
        "j": "ج",
        "H": "ح",
        "x": "خ",
        "d": "د",
        "*": "ذ",
        "r": "ر",
        "z": "ز",
        "s": "س",
        "$": "ش",
        "S": "ص",
        "D": "ض",
        "T": "ط",
        "Z": "ظ",
        "E": "ع",
        "g": "غ",
        "_": "ـ",
        "f": "ف",
        "q": "ق",
        "k": "ك",
        "l": "ل",
        "m": "م",
        "n": "ن",
        "h": "ه",
        "w": "و",
        "Y": "ى",
        "y": "ي",
        "F": "ً",
        "N": "ٌ",
        "K": "ٍ",
        "a": "َ",
        "u": "ُ",
        "i": "ِ",
        "~": "ّ",
        "o": "ْ",
        "`": "ٰ",
    }
)

_LEX_ID_SUFFIX = re.compile(r"_\d+$")


@dataclass(frozen=True)
class GoldWord:
    chapter_id: int
    verse_id: int
    word_id: int
    surface: str
    surface_norm: str
    pos_stem: str
    pos_segments: tuple[str, ...]
    lemma_raw: str
    lemma_norm: str
    segments_norm: tuple[str, ...]

    @property
    def verse_key(self) -> tuple[int, int]:
        return (self.chapter_id, self.verse_id)


def bw_to_arabic(text: str) -> str:
    return text.translate(_BW2AR)


def strip_lex_id(lemma: str) -> str:
    return _LEX_ID_SUFFIX.sub("", lemma.strip())


def normalize_lemma(raw: str, *, profile: str = "strict") -> str:
    cleaned = strip_lex_id(raw)
    if not cleaned or cleaned in {"_", "-", "NA", "na"}:
        return ""
    arabic = bw_to_arabic(cleaned) if _looks_like_buckwalter(cleaned) else cleaned
    return normalize(arabic, profile)  # type: ignore[arg-type]


def _looks_like_buckwalter(text: str) -> bool:
    """EQTB ``lemma`` jest BW; ``lemma_ar`` i CAMeL ``lex`` sa Unicode."""
    if not text:
        return False
    return any(ch in "AEHSTZD$&<>{}|'~`*" for ch in text) or (
        text.isascii() and any(ch.isalpha() for ch in text)
    )


def _stem_pos(segment_types: Sequence[str], pos_tags: Sequence[str]) -> str:
    for kind, pos in zip(segment_types, pos_tags, strict=True):
        if str(kind).strip().upper() == "STEM" and str(pos).strip():
            return str(pos).strip().upper()
    for pos in pos_tags:
        tag = str(pos).strip().upper()
        if tag and tag != "DET":
            return tag
    return str(pos_tags[0]).strip().upper() if pos_tags else ""


def _stem_lemma(segment_types: Sequence[str], lemmas: Sequence[str]) -> str:
    for kind, lemma in zip(segment_types, lemmas, strict=True):
        if str(kind).strip().upper() == "STEM":
            return str(lemma).strip()
    for lemma in lemmas:
        if str(lemma).strip() not in {"", "_"}:
            return str(lemma).strip()
    return ""


def load_gold_words(
    df: pd.DataFrame,
    *,
    profile: str = "strict",
    max_words: int | None = None,
) -> list[GoldWord]:
    """Z DataFrame EQTB (parquet T-009) buduje liste 77429 slow ortograficznych."""
    needed = {"chapter_id", "verse_id", "word_id", "imlaai_token", "pos"}
    missing = needed - set(df.columns)
    if missing:
        raise ValueError(f"EQTB bez kolumn {sorted(missing)}")

    real = df.loc[df["word_id"].astype(str).str.strip() != "0"].copy()
    real["_ch"] = real["chapter_id"].astype(int)
    real["_vs"] = real["verse_id"].astype(int)
    real["_wd"] = real["word_id"].astype(int)
    if "tok_id" in real.columns:
        real["_tok"] = pd.to_numeric(real["tok_id"], errors="coerce").fillna(0)
        real = real.sort_values(["_ch", "_vs", "_wd", "_tok"], kind="mergesort")
    else:
        real = real.sort_values(["_ch", "_vs", "_wd"], kind="mergesort")

    has_lemma_ar = "lemma_ar" in real.columns
    has_lemma = "lemma" in real.columns
    has_seg = "segment" in real.columns

    words: list[GoldWord] = []
    for _, group in real.groupby(["_ch", "_vs", "_wd"], sort=False):
        ch = int(group["_ch"].iloc[0])
        vs = int(group["_vs"].iloc[0])
        wd = int(group["_wd"].iloc[0])
        imlaai = [str(x) for x in group["imlaai_token"].tolist()]
        pos_tags = [str(x).strip() for x in group["pos"].tolist()]
        seg_types = (
            [str(x).strip() for x in group["segment"].tolist()]
            if has_seg
            else ["STEM"] * len(imlaai)
        )
        if has_lemma_ar:
            raw_lemmas = [str(x) for x in group["lemma_ar"].tolist()]
        elif has_lemma:
            raw_lemmas = [str(x) for x in group["lemma"].tolist()]
        else:
            raw_lemmas = [""] * len(imlaai)
        surface = "".join(imlaai)
        surface_norm = normalize(surface, profile)  # type: ignore[arg-type]
        segments_norm = tuple(normalize(tok, profile) for tok in imlaai)  # type: ignore[arg-type]
        lemma_raw = _stem_lemma(seg_types, raw_lemmas)
        words.append(
            GoldWord(
                chapter_id=ch,
                verse_id=vs,
                word_id=wd,
                surface=surface,
                surface_norm=surface_norm,
                pos_stem=_stem_pos(seg_types, pos_tags),
                pos_segments=tuple(p.upper() for p in pos_tags),
                lemma_raw=lemma_raw,
                lemma_norm=normalize_lemma(lemma_raw, profile=profile),
                segments_norm=segments_norm,
            )
        )
        if max_words is not None and len(words) >= max_words:
            break
    return words
