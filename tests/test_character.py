"""T-021: F1 char_wb, wariant bez ligatur, synthetic windows."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.config import load_config
from src.data.normalize_arabic import strip_diacritics_and_ligatures
from src.features.base import make_char_tfidf
from src.features.character import run_character_features
from src.paths import CONFIGS_DIR
from src.viz.fig40_character import SPEC


def test_char_vectorizer_uses_char_wb_not_char() -> None:
    vectorizer = make_char_tfidf(min_df=1, max_features=10)
    assert vectorizer.analyzer == "char_wb"
    assert vectorizer.analyzer != "char"
    assert vectorizer.ngram_range == (3, 5)
    assert vectorizer.lowercase is False


def test_ligature_variant_decomposes_presentation_form() -> None:
    # lam-alif presentation form U+FEFB
    raw = "\ufefbabc"
    out = strip_diacritics_and_ligatures(raw)
    assert "\ufefb" not in out
    assert out


def _write_windows(folder: Path, n_train: int = 12, n_test: int = 4, n_quran: int = 3) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    base = "aaa bbb ccc ddd eee fff aaa bbb ccc "
    ctrl_ids, ctrl_split, ctrl_text, ctrl_n = [], [], [], []
    for i in range(n_train):
        ctrl_ids.append(f"tr{i}")
        ctrl_split.append("ctrl_train")
        ctrl_text.append(base + f"train{i} extra token sequence")
        ctrl_n.append(12)
    for i in range(n_test):
        ctrl_ids.append(f"te{i}")
        ctrl_split.append("ctrl_test")
        ctrl_text.append(base + f"test{i} extra token sequence")
        ctrl_n.append(12)
    pq.write_table(
        pa.table(
            {
                "document_id": ctrl_ids,
                "corpus": ["ctrl"] * len(ctrl_ids),
                "split": ctrl_split,
                "text_norm_strict": ctrl_text,
                "n_tokens": ctrl_n,
            }
        ),
        folder / "ctrl.parquet",
    )
    pq.write_table(
        pa.table(
            {
                "document_id": [f"q{i}" for i in range(n_quran)],
                "corpus": ["quran"] * n_quran,
                "split": ["target"] * n_quran,
                "text_norm_strict": [base + f"quran{i} extra token sequence" for i in range(n_quran)],
                "n_tokens": [12] * n_quran,
            }
        ),
        folder / "quran.parquet",
    )


def test_run_character_on_synthetic_windows(tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    win = processed / "windows_400"
    _write_windows(win)
    config = load_config(CONFIGS_DIR / "base.yaml")
    payload = run_character_features(
        config,
        processed_dir=processed,
        features_root=tmp_path / "features",
        vectorizer_dir=tmp_path / "vec",
        skip_fig=True,
        min_df=1,
        max_features=80,
    )
    assert payload["n_ctrl_train"] == 12
    assert payload["variants"]["main"]["n_cols"] > 0
    assert payload["variants"]["no_diacritics_no_ligatures"]["n_cols"] > 0
    assert payload["variants"]["main"]["n_zero_rows"] == 0
    assert abs(float(payload["variants"]["main"]["norm_token"]["r"])) < 0.3


def test_fig40_declares_ctrl_test_control() -> None:
    assert SPEC.fig_id == "FIG-40"
    assert SPEC.kind == "result"
    assert "ctrl" in (SPEC.control_anchor or "").lower() and "test" in (SPEC.control_anchor or "").lower()
    assert "char_wb" in SPEC.shows.lower() or "n-gram" in SPEC.shows.lower()
