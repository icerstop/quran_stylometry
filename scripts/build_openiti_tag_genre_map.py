"""Buduje data/reference/openiti_tag_genre_map.csv z dowodami z TSV.

Mapowanie TYLKO tam, gdzie 3-5 unikalnych tytulow potwierdza gatunek.
Tagi rozwazone i odrzucone zostaja z mapped=false (slad dowodowy).
Kolejnosc wierszy mapped=true = priorytet §4 (pierwsze trafienie wygrywa).
"""

from __future__ import annotations

import csv
from collections import defaultdict

from src.data.download_openiti import load_metadata
from src.data.genre import parse_tags
from src.paths import TAG_GENRE_MAP_PATH

# (tag, genre, note) — genre puste = nie mapujemy.
# Kolejnosc = priorytet przy klasyfikacji (jak tabela tytulowa §4).
_DECISIONS: tuple[tuple[str, str, str], ...] = (
    # poetry_diwan — _SHICR* to diwany, nie retoryka
    ("_SHICR", "poetry_diwan", ""),
    ("_SHICR_CABBASI", "poetry_diwan", ""),
    ("_SHICR_JAHILI", "poetry_diwan", ""),
    ("_SHICR_UMAWI", "poetry_diwan", ""),
    ("_SHICR_CUTHMANI", "poetry_diwan", ""),
    ("_SHICR_ANDALUSI", "poetry_diwan", ""),
    # hadith_collection
    ("_HADITH", "hadith_collection", ""),
    ("_MASANID", "hadith_collection", ""),
    ("_SUNAN", "hadith_collection", ""),
    ("_SAHIH", "hadith_collection", ""),
    # tafsir
    ("_TAFSIR", "tafsir", ""),
    # history / geography / travel
    ("_TARIKH", "history", ""),
    ("_FUTUH", "history", ""),
    ("_JUGHRAFIYA", "history", ""),
    ("_DJUGHRAFIYA", "history", "wariant pisowni _JUGHRAFIYA"),
    ("_RIHLAT", "history", ""),
    ("_BULDAN", "", "geografia z nazwy, ale 5 unikalnych tytulow to fada'il/ansab/futuh — nie mapowane"),
    # biography
    ("_TABAQAT", "biography", ""),
    ("_WAFAYAT", "biography", ""),
    ("_SIRA", "biography", ""),
    ("_SHAMAIL", "biography", ""),
    ("_MUFASSIRUN", "biography", ""),
    # fiqh
    ("_FIQH", "fiqh", ""),
    ("_FATAWA", "fiqh", ""),
    ("_QADA", "fiqh", ""),
    ("_MASAIL", "fiqh", ""),
    # theology
    ("_CAQAID", "theology", ""),
    ("_MILAL", "theology", ""),
    ("_FIRAQ", "theology", ""),
    # adab_prose
    ("_AMALI", "adab_prose", ""),
    ("_AKHLAQ", "adab_prose", "etyka / adab; nie poezja"),
    # --- rozwazone, NIE mapowane (dowod w evidence_sample) ---
    ("_ADAB", "", "tytuly w TSV to glownie Diwan — koliduje z poetry_diwan; fallback tytulowy"),
    ("_BALAGHA", "", "retoryka + diwany; nie jednoznaczny gatunek z listy §4"),
    ("_ADHKAR", "", "empirycznie zuhd/adab, nie du'a/khutab; fallback tytulowy na prayer_sermon"),
    ("_TARAJIM", "", "probka mieszana (juz/jami/manasik/mashyakha), nie czysta biografistyka"),
    ("_QURAN", "", "mushaf / tekst Koranu, nie tafsir"),
    ("_AHKAM", "", "mieszane Ahkam Quran (tafsir) i ahkam fiqh"),
    ("_USUL", "", "usul fiqh / usul din — nie rozroznione"),
    ("_CILAL", "", "critica hadith, nie zbior kanoniczny"),
    ("_TAKHRIJ", "", "takhrij, nie zbior kanoniczny"),
    ("_FAWAID", "", "fawa'id / majalis, nie zbior kanoniczny"),
    ("_ANSAB", "", "tablice genealogiczne — EXCLUDE_TITLE_PATTERNS, nie gatunek"),
)


def _title_label(title_lat: str, book: str) -> str:
    title = (title_lat or "").strip()
    book = (book or "").strip()
    if title and title.lower() not in {"diwan", "tafsir", "amthal", "zuhd"}:
        return title
    if book:
        return f"{title} [{book}]" if title else book
    return title or "(brak tytulu)"


def unique_titles_for_tag(df, tag: str, *, n: int = 5) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for row in df.itertuples():
        if tag not in parse_tags(row.tags):
            continue
        label = _title_label(row.title_lat, row.book)
        key = label.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(label.replace("|", "/"))
        if len(out) >= n:
            break
    return out


def main() -> None:
    df = load_metadata()
    # Pelna tabela — inwentarz ma byc empiryczny wobec TSV, nie tylko puli T-011.
    counts: dict[str, int] = defaultdict(int)
    for row in df.itertuples():
        for tag in parse_tags(row.tags):
            counts[tag] += 1

    TAG_GENRE_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["tag", "genre", "n_in_tsv", "mapped", "evidence_sample", "note"]
    with TAG_GENRE_MAP_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for tag, genre, note in _DECISIONS:
            samples = unique_titles_for_tag(df, tag, n=5)
            mapped = bool(genre) and len(samples) >= 3
            if genre and len(samples) < 3:
                # ten sam standard co constituent_node: bez 3 tytulow nie mapujemy
                note = (
                    (note + "; " if note else "")
                    + f"za malo unikalnych tytulow ({len(samples)}) — nie mapowane"
                )
            writer.writerow(
                {
                    "tag": tag,
                    "genre": genre if mapped else "",
                    "n_in_tsv": counts.get(tag, 0),
                    "mapped": "true" if mapped else "false",
                    "evidence_sample": " | ".join(samples),
                    "note": note,
                }
            )
    n_mapped = sum(1 for _, g, _ in _DECISIONS if g)
    print(f"wrote {TAG_GENRE_MAP_PATH} decisions={len(_DECISIONS)} mapped_attempted={n_mapped}")


if __name__ == "__main__":
    main()
