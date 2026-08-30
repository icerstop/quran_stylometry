"""T-007 — kontrakty I/O (docs/03_DATA.md §9).

DoD: test odrzucajacy rekord bez `split` albo z `n_tokens=0`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from src.schemas import Chronology, ExperimentResult, Window
from src.utils.io import SchemaViolationError, read_model, write_model, write_models_jsonl


def window_kwargs(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "document_id": "quran_s002_w003",
        "corpus": "quran",
        "split": "target",
        "genre": "quran",
        "surah_id": 2,
        "surah_ids": [2],
        "verse_start": 141,
        "verse_end": 176,
        "n_tokens": 400,
        "n_segments": 663,
        "n_verses": 36,
        "mean_verse_len": 11.1,
        "normalizer_version": "strict-1.0.0",
        "tagger_version": "camel-tools-1.6.0",
    }
    payload.update(overrides)
    return payload


def test_valid_window_is_accepted() -> None:
    window = Window(**window_kwargs())
    assert window.n_tokens == 400
    assert window.split == "target"
    assert window.annotation_source == "predicted"


def test_window_without_split_is_rejected() -> None:
    payload = window_kwargs()
    del payload["split"]
    with pytest.raises(ValidationError, match="split"):
        Window(**payload)


def test_window_with_zero_tokens_is_rejected() -> None:
    with pytest.raises(ValidationError, match="n_tokens"):
        Window(**window_kwargs(n_tokens=0))


def test_window_with_negative_tokens_is_rejected() -> None:
    with pytest.raises(ValidationError, match="n_tokens"):
        Window(**window_kwargs(n_tokens=-5))


def test_unknown_field_is_rejected() -> None:
    """Literowka w nazwie pola nie moze przejsc niezauwazona."""
    with pytest.raises(ValidationError):
        Window(**window_kwargs(n_token=400))


def test_invalid_split_value_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Window(**window_kwargs(split="train"))


def test_non_composite_window_cannot_span_two_surahs() -> None:
    """G3 — okno nie przekracza granicy sury, chyba ze jest jawnie kompozytowe."""
    with pytest.raises(ValidationError, match="G3"):
        Window(**window_kwargs(surah_ids=[108, 109], composite=False))


def test_composite_window_may_span_surahs() -> None:
    window = Window(**window_kwargs(surah_id=108, surah_ids=[108, 109, 110], composite=True))
    assert window.composite is True
    assert len(window.surah_ids) == 3


def test_quran_window_must_not_carry_book_id() -> None:
    with pytest.raises(ValidationError, match="book_id"):
        Window(**window_kwargs(book_id="0525AH.Book"))


def test_ctrl_window_shape() -> None:
    window = Window(
        **window_kwargs(
            document_id="ctrl_0310AH_tabari_w0007",
            corpus="ctrl",
            split="ctrl_train",
            genre="tafsir",
            author_id="0310Tabari",
            book_id="0310Tabari.Tafsir",
            death_date_ah=310,
            period_bucket="near",
            surah_id=None,
            surah_ids=[],
            verse_start=None,
            verse_end=None,
            n_verses=0,
            mean_verse_len=None,
        )
    )
    assert window.period_bucket == "near"
    assert window.surah_id is None


def test_chronology_uses_decisions_column_names() -> None:
    """09_DECISIONS §2.4 wygrywa nad 03_DATA §9: bez `order_cairo`/`order_sadeghi`."""
    chrono = Chronology(
        period_traditional="medinan", order_canonical=2, order_traditional=87, order_noldeke=87
    )
    assert chrono.order_canonical == 2
    for removed in ("order_cairo", "order_sadeghi"):
        assert removed not in Chronology.model_fields

    with pytest.raises(ValidationError):
        Chronology(order_sadeghi=88)  # type: ignore[call-arg]


def test_gold_and_predicted_are_separate_containers() -> None:
    """Rozdzial na poziomie schematu — G1 nie da sie zlamac przez literowke."""
    window = Window(**window_kwargs())
    assert window.gold.is_empty()
    assert "pos_gold" not in type(window.predicted).model_fields
    assert "pos_pred" not in type(window.gold).model_fields


def test_experiment_result_requires_ci_when_uncertainty_declared() -> None:
    with pytest.raises(ValidationError, match="ci"):
        ExperimentResult(
            experiment_id="E-05",
            task="T-035",
            config_hash="abc",
            uncertainty_declared=True,
        )


def test_experiment_result_rejects_inverted_interval() -> None:
    with pytest.raises(ValidationError, match="lo, hi"):
        ExperimentResult(
            experiment_id="E-05",
            task="T-035",
            config_hash="abc",
            uncertainty_declared=True,
            ci={"v_med": [0.9, 0.1]},
        )


def test_experiment_result_may_declare_no_uncertainty() -> None:
    """Funkcja moze nie miec niepewnosci, ale musi to zadeklarowac jawnie."""
    result = ExperimentResult(
        experiment_id="E-00",
        task="T-009",
        config_hash="abc",
        uncertainty_declared=False,
        note="Statystyki opisowe korpusu — przedzialy nie maja tu sensu.",
    )
    assert result.uncertainty_declared is False


def test_roundtrip_write_then_read_validates(tmp_path: Path) -> None:
    path = tmp_path / "window.json"
    write_model(path, Window(**window_kwargs()))
    assert read_model(path, Window).document_id == "quran_s002_w003"


def test_reading_invalid_record_raises_schema_violation(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text('{"document_id": "x"}', encoding="utf-8")
    with pytest.raises(SchemaViolationError):
        read_model(path, Window)


def test_jsonl_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "windows.jsonl"
    windows = [Window(**window_kwargs(document_id=f"quran_s002_w{i:03d}")) for i in range(3)]
    write_models_jsonl(path, windows)
    assert len(path.read_text(encoding="utf-8").strip().splitlines()) == 3
