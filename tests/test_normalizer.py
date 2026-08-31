"""Normalizator — docs/03_DATA.md §4 / T-013."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data.normalize_arabic import normalize, normalize_tokens, token_count
from src.paths import REPO_ROOT

SNAPSHOT_PATH = REPO_ROOT / "tests" / "fixtures" / "normalizer_snapshot.json"


def _snapshot() -> list[dict]:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_snapshot_has_fifty_hand_written_cases() -> None:
    rows = _snapshot()
    assert len(rows) == 50
    assert {int(r["id"]) for r in rows} == set(range(1, 51))
    assert {r["profile"] for r in rows} <= {"strict", "light"}


@pytest.mark.parametrize("row", _snapshot(), ids=lambda r: f"{r['id']}_{r['profile']}")
def test_snapshot_case(row: dict) -> None:
    assert normalize(row["input"], row["profile"]) == row["expected"]


@pytest.mark.parametrize("profile", ["strict", "light"])
def test_idempotent_on_snapshot_inputs(profile: str) -> None:
    for row in _snapshot():
        once = normalize(row["input"], profile)  # type: ignore[arg-type]
        assert normalize(once, profile) == once  # type: ignore[arg-type]


def test_alif_variants_collapse_in_strict_profile() -> None:
    assert normalize("أإآٱ", "strict") == "اااا"


def test_eqtb_hamza_alif_collapses_like_madda() -> None:
    """Q33:56 EQTB imlaai ءامنوا vs OpenITI امنوا / آمنوا — ten sam kod, obie strony."""
    assert normalize("ءامنوا", "strict") == "امنوا"
    assert normalize("آمنوا", "strict") == "امنوا"
    assert normalize("ءامنوا", "strict") == normalize("آمنوا", "strict")
    assert normalize("ءامنوا", "light") == "ءامنوا"
    once = normalize("ءامنوا", "strict")
    assert normalize(once, "strict") == once

def test_light_profile_preserves_alif_variants() -> None:
    assert normalize("أإآٱ", "light") == "أإآٱ"
    assert normalize("موسى مدينة مؤمن", "light") == "موسى مدينة مؤمن"


def test_diacritics_removed_in_both_profiles() -> None:
    """03_DATA §4: light pomija pkt 5–6, nie pkt 4."""
    assert normalize("كِتَابٌ", "strict") == "كتاب"
    assert normalize("كِتَابٌ", "light") == "كتاب"


def test_quranic_pause_marks_and_sajda_are_removed() -> None:
    assert normalize("كتاب۝۩۞", "strict") == "كتاب"


def test_dagger_alif_and_wasla_are_handled_explicitly() -> None:
    assert "ٰ" not in normalize("الرحمٰن", "strict")
    assert normalize("ٱلكتاب", "strict") == "الكتاب"
    assert normalize("ٱلكتاب", "light") == "ٱلكتاب"


def test_token_count_is_stable_under_normalization() -> None:
    tokens = ["كِتَابٌ", "أَحْمَدُ", "موسى", "مدينة", "مؤمن", "ٱلكتاب"]
    for profile in ("strict", "light"):
        out = normalize_tokens(tokens, profile)  # type: ignore[arg-type]
        assert len(out) == len(tokens)
        assert all(tok != "" for tok in out)


def test_no_empty_tokens_on_arabic_words() -> None:
    text = "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"
    out = normalize_tokens(text.split(), "strict")
    assert token_count(" ".join(out)) == len(out) == 4
    assert all(out)


def test_unknown_profile_raises() -> None:
    with pytest.raises(ValueError, match="profil"):
        normalize("كتاب", "heavy")  # type: ignore[arg-type]


def test_openiti_markup_stripped_as_step_zero() -> None:
    raw = "#META# book_id: 1\n######OpenITI#\nمتن عربي PageV01P002"
    assert normalize(raw, "strict") == "متن عربي"
