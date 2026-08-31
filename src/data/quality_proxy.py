"""Proxy jakosci OCR/transkrypcji (docs/09_DECISIONS.md §3, krok 4).

Modul LICZY metryki. Odciecie progiem jest gatunkowo-zalezne i naleza
do `select_ctrl.py` / `passes_quality_thresholds`.
`long_line_ratio` jest nadal liczone (diagnostyka), ale NIE wchodzi do
filtra — check strukturalnie martwy przy lamaniu linii OpenITI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Arabski + spacja + interpunkcja (arabska i lacińska). Wszystko poza tym
# liczy sie jako "spoza zakresu" — proxy OCR / smieci / mARkdown nieusuniety.
_IN_RANGE = re.compile(
    r"["
    r"\u0600-\u06FF"  # Arabic
    r"\u0750-\u077F"  # Arabic Supplement
    r"\u08A0-\u08FF"  # Arabic Extended-A
    r"\uFB50-\uFDFF"  # Arabic Presentation Forms-A
    r"\uFE70-\uFEFF"  # Arabic Presentation Forms-B
    r"\s"
    r".,;:!?()\[\]\"'«»ـ…،؛؟ـ"
    r"]"
)

# Naglowek OpenITI i kamienie milowe mARkdown (07_TASKS T-011: usunac, policzyc).
_META_LINE = re.compile(r"^#(?:META|OpenITI|#)", re.IGNORECASE)
_MILESTONE = re.compile(r"PageV\d+P\d+|ms\d+|¶+")
_PAGE_MARK = re.compile(r"###\s*\|+")


@dataclass(frozen=True)
class QualityMetrics:
    n_chars_raw: int
    n_chars_clean: int
    n_markdown_chars_removed: int
    n_lines: int
    n_long_lines: int  # > 2000 znakow po czyszczeniu
    non_arabic_ratio: float
    mean_word_length: float
    long_line_ratio: float
    n_words: int


def strip_markdwn(text: str) -> tuple[str, int]:
    """Usuwa znaczniki strukturalne OpenITI. Zwraca (tekst, n_usunietych_znakow)."""
    kept: list[str] = []
    removed = 0
    for line in text.splitlines():
        if _META_LINE.match(line.strip()):
            removed += len(line) + 1
            continue
        cleaned = _PAGE_MARK.sub("", line)
        cleaned = _MILESTONE.sub("", cleaned)
        removed += len(line) - len(cleaned)
        kept.append(cleaned)
    return "\n".join(kept), removed


def compute_quality_metrics(text: str) -> QualityMetrics:
    cleaned, n_removed = strip_markdwn(text)
    n_raw = len(text)
    n_clean = len(cleaned)
    if n_clean == 0:
        return QualityMetrics(
            n_chars_raw=n_raw,
            n_chars_clean=0,
            n_markdown_chars_removed=n_removed,
            n_lines=0,
            n_long_lines=0,
            non_arabic_ratio=1.0,
            mean_word_length=0.0,
            long_line_ratio=1.0,
            n_words=0,
        )

    in_range = sum(1 for ch in cleaned if _IN_RANGE.match(ch))
    non_arabic_ratio = 1.0 - (in_range / n_clean)

    words = [w for w in re.split(r"\s+", cleaned) if w]
    mean_word_length = (sum(len(w) for w in words) / len(words)) if words else 0.0

    lines = cleaned.splitlines()
    n_lines = len(lines) or 1
    n_long = sum(1 for line in lines if len(line) > 2000)
    return QualityMetrics(
        n_chars_raw=n_raw,
        n_chars_clean=n_clean,
        n_markdown_chars_removed=n_removed,
        n_lines=n_lines,
        n_long_lines=n_long,
        non_arabic_ratio=non_arabic_ratio,
        mean_word_length=mean_word_length,
        long_line_ratio=n_long / n_lines,
        n_words=len(words),
    )


# 09_DECISIONS.md §3 krok 4: poezja/maqama maja krotsze tokeny (~2.87),
# to cecha gatunku, nie defekt OCR. Pozostale gatunki: 3.0–8.0.
SHORT_TOKEN_GENRES = frozenset({"poetry_diwan", "maqamat_saj"})
DEFAULT_MIN_WORD_LEN = 3.0
SHORT_TOKEN_MIN_WORD_LEN = 2.5
MAX_WORD_LEN = 8.0
MAX_NON_ARABIC = 0.05


def min_word_length_for_genre(genre: str) -> float:
    if genre in SHORT_TOKEN_GENRES:
        return SHORT_TOKEN_MIN_WORD_LEN
    return DEFAULT_MIN_WORD_LEN


def passes_quality_thresholds(
    metrics: QualityMetrics,
    *,
    genre: str = "other",
    max_non_arabic: float = MAX_NON_ARABIC,
    min_word_len: float | None = None,
    max_word_len: float = MAX_WORD_LEN,
) -> bool:
    """Filtr §3 krok 4. `long_line_ratio` usuniete — nie dodawaj progu zastepczego."""
    low = min_word_length_for_genre(genre) if min_word_len is None else min_word_len
    return metrics.non_arabic_ratio < max_non_arabic and low <= metrics.mean_word_length <= max_word_len
