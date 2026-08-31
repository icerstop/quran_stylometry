"""T-014 diagnostyka ADV: gold T/LOC, stub tagger, bez CAMeL."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.annotate.diagnose_adv import diagnose_adv
from src.annotate.tagger import StubTagger


def test_diagnose_adv_counts_gold_and_records_errors(tmp_path: Path) -> None:
    parquet = tmp_path / "eqtb.parquet"
    pd.DataFrame(
        {
            "chapter_id": ["2", "2", "2"],
            "verse_id": ["2", "2", "2"],
            "word_id": ["1", "2", "3"],
            "tok_id": ["1", "1", "1"],
            "imlaai_token": ["ثم", "كتاب", "هناك"],
            "pos": ["T", "N", "LOC"],
            "segment": ["STEM", "STEM", "STEM"],
            "lemma": ["vm", "ktb", "hnAk"],
            "lemma_ar": ["ثم", "كتاب", "هناك"],
        }
    ).to_parquet(parquet)
    out = tmp_path / "adv.json"
    payload = diagnose_adv(
        tagger=StubTagger(),
        eqtb_path=parquet,
        out_path=out,
        sample_n=5,
        seed=20260830,
    )
    assert payload["n_gold_adv"] == 2
    assert payload["n_gold_T"] == 1
    assert payload["n_gold_LOC"] == 1
    assert payload["n_scored"] == 2
    assert payload["n_correct_coarse"] == 0
    assert payload["pred_coarse_on_gold_adv"]["NOUN"] == 2
    assert "noun" in payload["diagnosis"].lower() or "NOUN" in payload["diagnosis"]
    assert len(payload["error_sample"]) == 2
    assert payload["error_sample"][0]["location"].startswith("2:2:")
    assert out.exists()
