"""T-014: gold EQTB na slowach ortograficznych + ewaluacja bez sieci / bez CAMeL."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.annotate.evaluate_tagger import evaluate_aligned_verse, evaluate_gold, run_quran_eval
from src.annotate.gold import GoldWord, bw_to_arabic, load_gold_words, normalize_lemma
from src.annotate.tagger import (
    PredictedWord,
    StubTagger,
    parse_bw_segments,
    predicted_from_analysis,
)
from src.cli import PENDING_STAGES, main


def _gold(
    surface: str,
    pos: str,
    *,
    lemma: str = "",
    segs: tuple[str, ...] | None = None,
    ch: int = 1,
    vs: int = 1,
    wd: int = 1,
) -> GoldWord:
    segs_n = segs or (surface,)
    return GoldWord(
        chapter_id=ch,
        verse_id=vs,
        word_id=wd,
        surface=surface,
        surface_norm=surface,
        pos_stem=pos,
        pos_segments=(pos,),
        lemma_raw=lemma or surface,
        lemma_norm=lemma or surface,
        segments_norm=segs_n,
    )


def test_load_gold_words_counts_orthographic_words_not_segments() -> None:
    df = pd.DataFrame(
        {
            "chapter_id": ["1", "1", "1", "1"],
            "verse_id": ["1", "1", "1", "1"],
            "word_id": ["0", "1", "1", "2"],
            "tok_id": ["0", "1", "2", "1"],
            "imlaai_token": ["_", "ب", "سم", "الله"],
            "pos": ["_", "P", "N", "PN"],
            "segment": ["_", "PREFIX", "STEM", "STEM"],
            "lemma": ["_", "_", "som", "{ll~ah"],
            "lemma_ar": ["_", "_", "اسم", "الله"],
        }
    )
    words = load_gold_words(df)
    assert len(words) == 2
    assert words[0].surface_norm  # بسم po normalize
    assert words[0].pos_stem == "N"
    assert words[1].pos_stem == "PN"
    assert words[0].lemma_norm  # ze STEM lemma_ar


def test_bw_lemma_normalizes_to_arabic() -> None:
    assert "ل" in bw_to_arabic("{ll~ah") or "ا" in bw_to_arabic("{ll~ah")
    assert normalize_lemma("{ll~ah")
    assert normalize_lemma("_") == ""
    assert normalize_lemma("كَتَب_1")


def test_alignment_not_index_changes_pos_score() -> None:
    gold = [_gold("bsm", "N", wd=1), _gold("allh", "PN", wd=2)]
    pred = [
        PredictedWord("b", "b", "prep", "P", "PREP", "b", "b", ("b",)),
        PredictedWord("sm", "sm", "noun", "N", "NOUN", "sm", "sm", ("sm",)),
        PredictedWord("allh", "allh", "noun_prop", "PN", "NOUN", "allh", "allh", ("allh",)),
    ]
    stats = evaluate_aligned_verse(gold, pred)
    assert stats["n_gold"] == 2
    assert stats["n_pred"] == 3
    assert stats["n_aligned"] == 2
    # Zip po indeksie polaczylby allh gold z sm pred. Edit-distance laczy allh-allh.
    assert stats["per_pos"]["PN"][0] == 1


def test_evaluate_gold_with_stub_is_perfect_on_identity() -> None:
    gold = [
        _gold("ktab", "N", lemma="ktab", ch=1, vs=1, wd=1),
        _gold("allh", "PN", lemma="allh", ch=1, vs=1, wd=2),
        _gold("ktb", "V", lemma="ktb", ch=1, vs=2, wd=1),
    ]

    def _pw(tok: str, raw: str, eqtb: str, coarse: str) -> PredictedWord:
        return PredictedWord(tok, tok, raw, eqtb, coarse, tok, tok, (tok,))

    tagger = StubTagger(
        {
            ("ktab", "allh"): [
                _pw("ktab", "noun", "N", "NOUN"),
                _pw("allh", "noun_prop", "PN", "NOUN"),
            ],
            ("ktb",): [_pw("ktb", "verb", "V", "VERB")],
        }
    )
    metrics = evaluate_gold(gold, tagger)
    assert metrics["n_words"] == 3
    assert metrics["n_verses"] == 2
    assert metrics["pos_accuracy_coarse"] == 1.0
    assert metrics["pos_accuracy"] == 1.0
    assert metrics["lemma_accuracy"] == 1.0
    assert metrics["segmentation_f1"] == 1.0
    assert metrics["alignment_coverage"] == 1.0
    assert metrics["majority_baseline_coarse"] < 1.0


def test_run_quran_eval_writes_json_without_camel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parquet = tmp_path / "eqtb.parquet"
    pd.DataFrame(
        {
            "chapter_id": ["1", "1"],
            "verse_id": ["1", "1"],
            "word_id": ["1", "2"],
            "tok_id": ["1", "1"],
            "imlaai_token": ["كتاب", "الله"],
            "pos": ["N", "PN"],
            "segment": ["STEM", "STEM"],
            "lemma": ["ktb", "{llh"],
            "lemma_ar": ["كتاب", "الله"],
        }
    ).to_parquet(parquet)

    out = tmp_path / "tagger_eval.json"
    payload = run_quran_eval(
        tagger=StubTagger(),
        eqtb_path=parquet,
        out_path=out,
        write_figure=False,
        config_hash="test",
    )
    assert out.exists()
    assert payload["scope"] == "quran_only"
    assert payload["ctrl_tagged"] is False
    assert payload["handoff_h1_prepared"] is False
    assert payload["reference_corpus"] == "eqtb"
    assert payload["qac_status"] == "fallback_active"
    assert payload["metrics"]["pos_accuracy_coarse"] == 1.0
    assert '"farasa"' not in out.read_text(encoding="utf-8").lower()


def test_parse_bw_segments_splits_on_plus() -> None:
    segs = parse_bw_segments("bi/PREP+som/NOUN")
    assert len(segs) == 2
    pred = predicted_from_analysis("بسم", {"pos": "noun", "lex": "som_1", "bw": "bi/PREP+som/NOUN"})
    assert pred.pos_eqtb == "N"
    assert pred.pos_coarse == "NOUN"


def test_tag_is_not_a_pending_stage() -> None:
    assert "tag" not in PENDING_STAGES
    assert "tag-ctrl" not in PENDING_STAGES


def test_cli_tag_missing_parquet_fails_loudly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["tag", "--eqtb", str(tmp_path / "brak.parquet"), "--skip-fig"]) == 1
    assert "BLAD" in capsys.readouterr().err


def test_no_farasa_backend_in_annotate_package() -> None:
    import src.annotate.evaluate_tagger as ev
    import src.annotate.tagger as tg

    for module in (ev, tg):
        source = Path(module.__file__).read_text(encoding="utf-8")
        lowered = source.lower()
        assert "import farasa" not in lowered
        assert "from farasa" not in lowered
        assert "backend: farasa" not in lowered
        assert 'backend="farasa"' not in lowered


def test_fig39_writes_diagnostic_bundle(tmp_path: Path) -> None:
    from src.viz.fig39_tagger_eval import run as run_fig

    payload = {
        "per_pos_coarse": {
            "NOUN": {"correct": 8, "n": 10, "accuracy": 0.8},
            "VERB": {"correct": 1, "n": 5, "accuracy": 0.2},
        },
        "metrics": {
            "majority_baseline_coarse": 0.5,
            "pos_accuracy_coarse": 0.6,
        },
        "reference_corpus": "eqtb",
        "n_words": 15,
    }
    saved = run_fig(payload, config_hash="test", out_dir=tmp_path, index_path=tmp_path / "INDEX.md")
    assert saved.png.exists() and saved.svg.exists() and saved.json.exists()
    index = (tmp_path / "INDEX.md").read_text(encoding="utf-8")
    assert "FIG-39" in index
    assert "majority" in index.lower()
