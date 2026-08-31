"""T-022: F2 function words — segmentacja, G4, whitelist POS."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.config import load_config
from src.features.function_words import (
    POS_WHITELIST,
    expand_morph_pred,
    expand_tagged_word,
    is_function_pos,
    run_function_word_features,
)
from src.paths import CONFIGS_DIR
from src.schemas import GuardrailViolationError
from src.viz.fig41_function import SPEC


def test_bism_splits_prep_from_stem() -> None:
    segs = expand_morph_pred("ب+سم", "NOUN")
    assert segs == [("ب", "PREP"), ("سم", "NOUN")]
    forms = [f for f, p in segs if is_function_pos(p)]
    assert forms == ["ب"]


def test_wa_noun_and_enclitic_pronoun() -> None:
    segs = expand_morph_pred("و+امير+ه", "NOUN")
    assert segs[0] == ("و", "CONJ")
    assert segs[-1] == ("ه", "PRON")
    assert segs[1][1] == "NOUN"


def test_al_is_segmented_but_det_not_in_whitelist() -> None:
    segs = expand_morph_pred("ال+رحمن", "ADJ")
    assert segs[0] == ("ال", "DET")
    assert not is_function_pos("DET")
    assert "DET" not in POS_WHITELIST


def test_unsegmented_token_raises() -> None:
    with pytest.raises(GuardrailViolationError, match="segmentacji"):
        expand_tagged_word(token="والكتاب", pos_pred="NOUN", morph_pred="", bw_pred="")


def test_bw_proclitic_has_own_pos() -> None:
    segs = expand_tagged_word(
        token="بسم",
        pos_pred="NOUN",
        morph_pred="",
        bw_pred="bi/PREP+som/NOUN",
    )
    assert segs[0][1] == "PREP"
    assert is_function_pos(segs[0][1])


def test_fig41_declares_ctrl_test_control() -> None:
    assert SPEC.fig_id == "FIG-41"
    assert SPEC.kind == "result"
    anchor = (SPEC.control_anchor or "").lower()
    assert "ctrl" in anchor and "test" in anchor


def _write_book(
    *,
    tagged_dir: Path,
    clean_dir: Path,
    name: str,
    tokens: list[str],
    morph: list[str],
    pos: list[str],
) -> None:
    tagged_dir.mkdir(parents=True, exist_ok=True)
    clean_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "token": tokens,
            "pos_pred": pos,
            "pos_raw_pred": ["prep" if p == "PREP" else "noun" for p in pos],
            "lemma_pred": tokens,
            "morph_pred": morph,
        }
    ).to_parquet(tagged_dir / f"{name}.parquet", index=False)
    (clean_dir / name).write_text(" ".join(tokens), encoding="utf-8")


def test_run_function_words_on_synthetic(tmp_path: Path) -> None:
    tokens = ["بسم", "الله", "وكتاب", "في", "بيت"] * 8
    morph = ["ب+سم", "الله", "و+كتاب", "في", "بيت"] * 8
    pos = ["NOUN", "NOUN", "NOUN", "PREP", "NOUN"] * 8
    tagged = tmp_path / "tagged"
    clean = tmp_path / "clean"
    processed = tmp_path / "processed"
    win = processed / "windows_400"
    win.mkdir(parents=True)

    ctrl_rows = []
    for i in range(8):
        name = f"book_tr{i}"
        _write_book(
            tagged_dir=tagged, clean_dir=clean, name=name, tokens=tokens, morph=morph, pos=pos
        )
        ctrl_rows.append(
            {
                "document_id": f"ctrl_{name}_w0000",
                "corpus": "ctrl",
                "split": "ctrl_train",
                "text_norm_strict": " ".join(tokens),
                "n_tokens": len(tokens),
                "version_id": name,
            }
        )
    _write_book(
        tagged_dir=tagged, clean_dir=clean, name="book_test", tokens=tokens, morph=morph, pos=pos
    )
    ctrl_rows.append(
        {
            "document_id": "ctrl_book_test_w0000",
            "corpus": "ctrl",
            "split": "ctrl_test",
            "text_norm_strict": " ".join(tokens),
            "n_tokens": len(tokens),
            "version_id": "book_test",
        }
    )
    pd.DataFrame(ctrl_rows).to_parquet(win / "ctrl.parquet", index=False)

    q_tok = tokens[:20]
    pd.DataFrame(
        [
            {
                "document_id": "quran_s001_w000",
                "corpus": "quran",
                "split": "target",
                "text_norm_strict": " ".join(q_tok),
                "n_tokens": len(q_tok),
                "tokens": q_tok,
            }
        ]
    ).to_parquet(win / "quran.parquet", index=False)
    qtagged = tmp_path / "quran_tagged.parquet"
    pd.DataFrame(
        {
            "token": q_tok,
            "pos_pred": pos[:20],
            "pos_raw_pred": ["noun"] * 20,
            "lemma_pred": q_tok,
            "morph_pred": morph[:20],
            "bw_pred": [""] * 20,
            "surah_id": [1] * 20,
            "verse_id": [1] * 20,
            "word_id": list(range(20)),
        }
    ).to_parquet(qtagged, index=False)

    config = load_config(CONFIGS_DIR / "base.yaml")
    payload = run_function_word_features(
        config,
        processed_dir=processed,
        features_root=tmp_path / "features",
        vectorizer_dir=tmp_path / "vec",
        tagged_dir=tagged,
        clean_dir=clean,
        quran_tagged=qtagged,
        skip_fig=True,
        k_grid=[3],
    )
    assert payload["n_ctrl_train"] == 8
    assert payload["variants"]["k3"]["n_cols"] == 3
    assert payload["variants"]["k3"]["n_zero_rows"] == 0
    assert abs(float(payload["variants"]["k3"]["norm_token"]["r"])) < 0.3
