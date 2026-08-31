"""T-023: F3 lexical TF-IDF (word/lemma/root), G4, predicted-only."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import load_config
from src.features.base import make_lexical_tfidf
from src.features.lexical import join_field, run_lexical_features
from src.paths import CONFIGS_DIR
from src.viz.fig42_lexical import SPEC


def test_lexical_vectorizer_is_word_1_2_not_char() -> None:
    vectorizer = make_lexical_tfidf(min_df=1)
    assert vectorizer.analyzer == "word"
    assert vectorizer.ngram_range == (1, 2)
    assert vectorizer.lowercase is False
    assert vectorizer.tokenizer is str.split


def test_join_field_skips_empty_not_surface() -> None:
    assert join_field(["كتب", "", "_", "قال"]) == "كتب قال"


def test_fig42_declares_ctrl_test_control() -> None:
    assert SPEC.fig_id == "FIG-42"
    assert SPEC.kind == "result"
    assert SPEC.families == ["lexical"]
    anchor = (SPEC.control_anchor or "").lower()
    assert "ctrl" in anchor and "test" in anchor


def _write_book(
    *,
    tagged_dir: Path,
    clean_dir: Path,
    name: str,
    tokens: list[str],
    lemmas: list[str],
    roots: list[str],
) -> None:
    tagged_dir.mkdir(parents=True, exist_ok=True)
    clean_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "token": tokens,
            "pos_pred": ["NOUN"] * len(tokens),
            "pos_raw_pred": ["noun"] * len(tokens),
            "lemma_pred": lemmas,
            "morph_pred": [f"و+{t}" if i % 3 == 0 else t for i, t in enumerate(tokens)],
            "root_pred": roots,
        }
    ).to_parquet(tagged_dir / f"{name}.parquet", index=False)
    (clean_dir / name).write_text(" ".join(tokens), encoding="utf-8")


def test_run_lexical_on_synthetic(tmp_path: Path) -> None:
    tokens = ["كتاب", "الله", "قال", "في", "بيت"] * 8
    lemmas = ["كتاب", "الله", "قال", "في", "بيت"] * 8
    roots = ["ك.ت.ب", "#.ل.ه", "ق.و.ل", "ف.ي", "ب.ي.ت"] * 8
    tagged = tmp_path / "tagged"
    clean = tmp_path / "clean"
    processed = tmp_path / "processed"
    win = processed / "windows_400"
    win.mkdir(parents=True)
    ctrl_rows = []
    for i in range(8):
        name = f"book_tr{i}"
        _write_book(
            tagged_dir=tagged,
            clean_dir=clean,
            name=name,
            tokens=tokens,
            lemmas=lemmas,
            roots=roots,
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
        tagged_dir=tagged,
        clean_dir=clean,
        name="book_test",
        tokens=tokens,
        lemmas=lemmas,
        roots=roots,
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
            "pos_pred": ["NOUN"] * 20,
            "pos_raw_pred": ["noun"] * 20,
            "lemma_pred": lemmas[:20],
            "morph_pred": q_tok,
            "root_pred": roots[:20],
            "bw_pred": [""] * 20,
            "surah_id": [1] * 20,
            "verse_id": [1] * 20,
            "word_id": list(range(20)),
        }
    ).to_parquet(qtagged, index=False)

    config = load_config(CONFIGS_DIR / "base.yaml")
    payload = run_lexical_features(
        config,
        processed_dir=processed,
        features_root=tmp_path / "features",
        vectorizer_dir=tmp_path / "vec",
        tagged_dir=tagged,
        clean_dir=clean,
        quran_tagged=qtagged,
        skip_fig=True,
        min_df=1,
        analyzer=object(),
        units=["word", "lemma", "root"],
    )
    assert payload["n_ctrl_train"] == 8
    for unit in ("word", "lemma", "root"):
        assert payload["variants"][unit]["n_cols"] > 0
        assert payload["variants"][unit]["n_zero_rows"] == 0
        assert abs(float(payload["variants"][unit]["norm_token"]["r"])) < 0.3
    assert "word" in payload["variants"]["word"]["dir"]
