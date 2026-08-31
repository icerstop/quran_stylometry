"""Reguły gatunku z docs/09_DECISIONS.md §4 — pierwsze trafienie wygrywa."""

from __future__ import annotations

from pathlib import Path

from src.data.genre import (
    assign_genre,
    assign_genre_two_stage,
    is_excluded_title,
    justification_note,
    normalize_title,
    write_genres_csv,
)


def test_first_match_wins_maqama_over_adab() -> None:
    assert assign_genre(title_lat="Maqamat al-Adab") == "maqamat_saj"


def test_diwan_and_arabic_poetry() -> None:
    assert assign_genre(title_lat="Diwan Abi Nuwas") == "poetry_diwan"
    assert assign_genre(title_ar="ديوان المتنبي") == "poetry_diwan"


def test_tafsir_ahkam_quran_beats_fiqh_ahkam() -> None:
    """Kolejnosc: tafsir (4) przed fiqh (8) — ahkam al-qur'an to tafsir."""
    assert assign_genre(title_lat="Ahkam al-Qur'an") == "tafsir"
    assert assign_genre(title_lat="Kitab al-Ahkam") == "fiqh"


def test_hadith_and_prayer_and_history() -> None:
    assert assign_genre(title_lat="Sahih al-Bukhari") == "hadith_collection"
    assert assign_genre(title_lat="al-Sahifa al-Sajjadiyya") == "prayer_sermon"
    assert assign_genre(title_lat="Tarikh al-Tabari") == "history"


def test_book_slug_is_used_when_titles_empty() -> None:
    assert assign_genre(book="0001AbuTalibCabdManaf.Diwan") == "poetry_diwan"


def test_unmatched_is_other() -> None:
    assert assign_genre(title_lat="Kitab al-Hayawan") == "other"


def test_normalize_strips_diacritics_and_apostrophes() -> None:
    assert normalize_title("Tafsīr al-Qurʾān") == "tafsir al-quran"
    assert "َ" not in normalize_title("تَفْسِير")


def test_exclude_dictionaries_and_gazetteers() -> None:
    assert is_excluded_title(title_lat="Lisan al-Arab")
    assert is_excluded_title(title_lat="Mu'jam al-Buldan")
    assert not is_excluded_title(title_lat="Sahih Muslim")


def test_two_stage_tag_beats_title(tmp_path: Path) -> None:
    mapping = tmp_path / "map.csv"
    mapping.write_text(
        "tag,genre,n_in_tsv,mapped,evidence_sample,note\n"
        "_SHICR,poetry_diwan,10,true,Diwan A | Diwan B | Diwan C,\n"
        "_HADITH,hadith_collection,10,true,Sahih | Sunan | Musnad,\n",
        encoding="utf-8",
    )
    tagged = assign_genre_two_stage(
        tags="CLEANED_VERSION _HADITH _TARAJIM",
        title_lat="Tabaqat al-Fuqaha",
        map_path=str(mapping),
    )
    assert tagged.genre == "hadith_collection"
    assert tagged.source == "tag:_HADITH"


def test_two_stage_falls_back_to_title_when_tag_unmapped(tmp_path: Path) -> None:
    mapping = tmp_path / "map.csv"
    mapping.write_text(
        "tag,genre,n_in_tsv,mapped,evidence_sample,note\n"
        "_ADAB,,780,false,Diwan | Diwan | Amthal,odrzucone\n",
        encoding="utf-8",
    )
    hit = assign_genre_two_stage(
        tags="CLEANED_VERSION _ADAB",
        title_lat="Diwan Abi Nuwas",
        map_path=str(mapping),
    )
    assert hit.genre == "poetry_diwan"
    assert hit.source == "title"


def test_two_stage_residual_other_is_allowed(tmp_path: Path) -> None:
    mapping = tmp_path / "map.csv"
    mapping.write_text(
        "tag,genre,n_in_tsv,mapped,evidence_sample,note\n",
        encoding="utf-8",
    )
    residual = assign_genre_two_stage(
        tags="CLEANED_VERSION",
        title_lat="Kitab al-Hayawan",
        map_path=str(mapping),
    )
    assert residual.genre == "other"
    assert residual.source == "other"


def test_justification_note_covers_three_sources() -> None:
    assert "openiti_tag_genre_map.csv" in justification_note("hadith_collection", "tag:_HADITH")
    assert "krok 2" in justification_note("poetry_diwan", "title")
    assert "residual other" in justification_note("other", "other")


def test_write_genres_csv_adds_note_without_reclassifying(tmp_path: Path) -> None:
    import pandas as pd

    manifest = pd.DataFrame(
        [
            {
                "version_uri": "a.Sahih-ara1",
                "book": "a.Sahih",
                "author_id": "a",
                "genre": "hadith_collection",
                "genre_source": "tag:_SAHIH",
                "author_genre": "hadith_collection",
                "admission_path": "standard",
            }
        ]
    )
    out = write_genres_csv(manifest, path=tmp_path / "genres.csv")
    table = pd.read_csv(out)
    assert list(table["genre"]) == ["hadith_collection"]
    assert "note" in table.columns
    assert "_SAHIH" in table.iloc[0]["note"]
