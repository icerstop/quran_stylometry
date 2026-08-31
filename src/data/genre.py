"""Klasyfikacja gatunku (docs/09_DECISIONS.md §4).

Dwustopniowa:
  1. tagi OpenITI z `data/reference/openiti_tag_genre_map.csv` (sygnal glowny)
  2. wzorce tytulowe ponizej — tylko gdy (1) nie dal wyniku
  3. residual `other` (akceptowane; nie forsuj dopasowania)

Kolejnosc tagow w CSV = priorytet (to samo co kolejnosc regul tytulowych).
Pierwsze trafienie wygrywa. Wejscie tytulowe: title_lat, title_ar, book.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Literal, NamedTuple

import pandas as pd

from src.paths import TAG_GENRE_MAP_PATH

GenreLabel = Literal[
    "maqamat_saj",
    "poetry_diwan",
    "hadith_collection",
    "tafsir",
    "prayer_sermon",
    "history",
    "biography",
    "fiqh",
    "theology",
    "adab_prose",
    "other",
]

# Kolejnosc = priorytet (pierwsze trafienie wygrywa). Wzorce stosowane do
# znormalizowanego tytulu (lowercase, bez diakrytyki, apostrofy sciagniete).
_GENRE_RULES: tuple[tuple[GenreLabel, tuple[str, ...]], ...] = (
    ("maqamat_saj", (r"maqam", r"مقام")),
    ("poetry_diwan", (r"diwan", r"ديوان", r"shi.?r", r"شعر")),
    (
        "hadith_collection",
        (r"sahih", r"sunan", r"musnad", r"muwatta", r"صحيح", r"سنن", r"مسند"),
    ),
    (
        "tafsir",
        (r"tafsir", r"تفسير", r"jami.?al.?bayan", r"ahkam.?al.?qur"),
    ),
    (
        "prayer_sermon",
        (r"du.?a\b", r"دعاء", r"sahifa", r"khutab", r"خطب", r"munajat"),
    ),
    ("history", (r"tarikh", r"تاريخ", r"akhbar", r"اخبار", r"futuh")),
    (
        "biography",
        (
            r"tabaqat",
            r"طبقات",
            r"\bsira\b",
            r"سيرة",
            r"wafayat",
            r"mujam.?al.?udaba",
        ),
    ),
    ("fiqh", (r"fiqh", r"فقه", r"mabsut", r"\bumm\b", r"hidaya", r"ahkam")),
    (
        "theology",
        (r"kalam", r"كلام", r"aqida", r"عقيدة", r"milal", r"usul.?al.?din"),
    ),
    (
        "adab_prose",
        (r"adab", r"ادب", r"\bbayan\b", r"amali", r"nawadir", r"rasail"),
    ),
)

# Krok 5 algorytmu: dziela bez autorskiego glosu. Osobno od gatunku.
_EXCLUDE_PATTERNS: tuple[str, ...] = (
    r"lisan.?al.?arab",
    r"\bqamus\b",
    r"\bsihah\b",
    r"taj.?al.?arus",
    r"fahras",
    r"kashf.?al.?zunun",
    r"\bansab\b",
    r"mujam.?al.?buldan",
)

_GENRE_COMPILED = tuple(
    (label, tuple(re.compile(p) for p in pats)) for label, pats in _GENRE_RULES
)
_EXCLUDE_COMPILED = tuple(re.compile(p) for p in _EXCLUDE_PATTERNS)

_ARABIC_DIACRITICS = re.compile(r"[\u064b-\u065f\u0670\u0640]")
_ALIF = str.maketrans("أإآٱ", "اااا")


def normalize_title(text: str) -> str:
    """Lowercase, bez diakrytyki, apostrofy i macrony sciagniete — wspolna
    przestrzen dla title_lat i title_ar (09_DECISIONS.md §4)."""
    folded = unicodedata.normalize("NFKD", text or "")
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = folded.lower().replace("ى", "ي").translate(_ALIF)
    folded = _ARABIC_DIACRITICS.sub("", folded)
    for src, dst in (
        ("ʿ", ""),
        ("ʾ", ""),
        ("'", ""),
        ("`", ""),
        ("’", ""),
        ("‘", ""),
        ("ā", "a"),
        ("ī", "i"),
        ("ū", "u"),
        ("ē", "e"),
        ("ō", "o"),
    ):
        folded = folded.replace(src, dst)
    return re.sub(r"\s+", " ", folded).strip()


def title_blob(title_lat: str = "", title_ar: str = "", book: str = "") -> str:
    """Laczy pola tytulowe. Z `book` (AUTHOR.Title) bierze czesc po pierwszej kropce."""
    book_title = book.split(".", 1)[1] if "." in book else book
    return normalize_title(" ".join(part for part in (title_lat, title_ar, book_title) if part))


def assign_genre(title_lat: str = "", title_ar: str = "", book: str = "") -> GenreLabel:
    blob = title_blob(title_lat, title_ar, book)
    if not blob:
        return "other"
    for label, patterns in _GENRE_COMPILED:
        if any(p.search(blob) for p in patterns):
            return label
    return "other"


def is_excluded_title(title_lat: str = "", title_ar: str = "", book: str = "") -> bool:
    blob = title_blob(title_lat, title_ar, book)
    return any(p.search(blob) for p in _EXCLUDE_COMPILED)


_TAG_SPLIT = re.compile(r"[\s:]+")


def parse_tags(tagstr: str) -> frozenset[str]:
    """Tagi OpenITI sa oddzielone spacjami albo `:::`. Zwraca zbior tokenow."""
    parts: set[str] = set()
    for chunk in str(tagstr or "").replace(":::", " ").split():
        token = chunk.strip().strip(":")
        if token and token not in {"-", "|"}:
            parts.add(token)
    return frozenset(parts)


class TagMapRow(NamedTuple):
    tag: str
    genre: GenreLabel | None
    n_in_tsv: int
    mapped: bool
    evidence_sample: str
    note: str


@lru_cache(maxsize=4)
def load_tag_genre_map(path: str | None = None) -> tuple[TagMapRow, ...]:
    target = Path(path) if path else TAG_GENRE_MAP_PATH
    rows: list[TagMapRow] = []
    with target.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            mapped = str(raw.get("mapped", "")).strip().lower() in {"1", "true", "yes"}
            genre_raw = (raw.get("genre") or "").strip()
            genre: GenreLabel | None = genre_raw if mapped and genre_raw else None  # type: ignore[assignment]
            n_raw = (raw.get("n_in_tsv") or "").strip()
            rows.append(
                TagMapRow(
                    tag=str(raw["tag"]).strip(),
                    genre=genre,
                    n_in_tsv=int(n_raw) if n_raw else 0,
                    mapped=mapped,
                    evidence_sample=str(raw.get("evidence_sample") or ""),
                    note=str(raw.get("note") or ""),
                )
            )
    return tuple(rows)


def mapped_tag_priority(path: str | None = None) -> tuple[tuple[str, GenreLabel], ...]:
    """Tylko wiersze `mapped=true`, w kolejnosci CSV (= priorytet §4)."""
    return tuple((row.tag, row.genre) for row in load_tag_genre_map(path) if row.mapped and row.genre)


class GenreAssignment(NamedTuple):
    genre: GenreLabel
    source: str  # "tag:_HADITH" | "title" | "other"


def assign_genre_from_tags(
    tags: frozenset[str] | set[str] | str,
    *,
    map_path: str | None = None,
) -> GenreAssignment | None:
    tagset = parse_tags(tags) if isinstance(tags, str) else frozenset(tags)
    for tag, genre in mapped_tag_priority(map_path):
        if tag in tagset:
            return GenreAssignment(genre, f"tag:{tag}")
    return None


def assign_genre_two_stage(
    *,
    tags: str = "",
    title_lat: str = "",
    title_ar: str = "",
    book: str = "",
    map_path: str | None = None,
) -> GenreAssignment:
    """§4: tagi, potem tytul, potem other. Nie forsuje dopasowania."""
    tagged = assign_genre_from_tags(tags, map_path=map_path)
    if tagged is not None:
        return tagged
    title_genre = assign_genre(title_lat=title_lat, title_ar=title_ar, book=book)
    if title_genre != "other":
        return GenreAssignment(title_genre, "title")
    return GenreAssignment("other", "other")


def justification_note(genre: str, genre_source: str) -> str:
    """Uzasadnienie etykiety — T-012 DoD, bez ponownej klasyfikacji."""
    source = genre_source or "other"
    if source.startswith("tag:"):
        tag = source.split(":", 1)[1]
        return (
            f"tag OpenITI {tag} → {genre} "
            f"(data/reference/openiti_tag_genre_map.csv, 09_DECISIONS.md §4 krok 1)"
        )
    if source == "title":
        return f"fallback tytulowy → {genre} (09_DECISIONS.md §4 krok 2)"
    return f"residual other (09_DECISIONS.md §4 krok 3; brak zmapowanego tagu i wzorca tytulu)"


def write_genres_csv(manifest: pd.DataFrame, path: Path | None = None) -> Path:
    """Eksport etykiet z manifestu T-011. Nie liczy gatunku od nowa."""
    from src.paths import GENRES_PATH
    from src.utils.io import ensure_dir

    target = path or GENRES_PATH
    work = manifest.copy()
    work["note"] = [
        justification_note(str(g), str(s))
        for g, s in zip(work["genre"], work["genre_source"], strict=True)
    ]
    cols = [
        c
        for c in (
            "version_uri",
            "book",
            "author_id",
            "genre",
            "genre_source",
            "author_genre",
            "admission_path",
            "note",
        )
        if c in work.columns
    ]
    ensure_dir(target.parent)
    work.loc[:, cols].sort_values(["genre", "author_id", "book"]).to_csv(
        target, index=False, encoding="utf-8", lineterminator="\n"
    )
    return target
