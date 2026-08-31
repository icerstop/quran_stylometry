"""Proxy jakosci — testowane na syntetycznym tekscie (08_REPO.md §3)."""

from __future__ import annotations

from dataclasses import replace

from src.data.quality_proxy import compute_quality_metrics, passes_quality_thresholds, strip_markdwn


def test_strip_markdwn_removes_meta_and_page_markers() -> None:
    raw = "#META# header\nمتن عربي\n### | PageV01P002\n"
    cleaned, n_removed = strip_markdwn(raw)
    assert "META" not in cleaned
    assert "PageV01P002" not in cleaned
    assert "متن عربي" in cleaned
    assert n_removed > 0


def test_clean_arabic_prose_passes_default_thresholds() -> None:
    text = "هذا كتاب في الادب والتاريخ " * 40
    metrics = compute_quality_metrics(text)
    assert metrics.non_arabic_ratio < 0.05
    assert 3.0 <= metrics.mean_word_length <= 8.0
    assert passes_quality_thresholds(metrics)


def test_latin_ocr_garbage_fails_non_arabic_ratio() -> None:
    text = "lorem ipsum dolor sit amet " * 40
    metrics = compute_quality_metrics(text)
    assert metrics.non_arabic_ratio > 0.5
    assert not passes_quality_thresholds(metrics)


def test_glued_tokens_fail_mean_word_length() -> None:
    text = "هذاكتاببدونمسافاتهذاكتاببدونمسافات " * 20
    metrics = compute_quality_metrics(text)
    assert metrics.mean_word_length > 8.0
    assert not passes_quality_thresholds(metrics)


def test_poetry_mean_word_length_2_87_passes_only_for_short_token_genres() -> None:
    """§3: dolny prog 2.5 dla poetry_diwan/maqamat_saj, 3.0 dla reszty."""
    metrics = compute_quality_metrics("هذا هو بيت شعر قصير " * 30)
    poetry_like = replace(metrics, mean_word_length=2.87, non_arabic_ratio=0.01)
    assert passes_quality_thresholds(poetry_like, genre="poetry_diwan")
    assert passes_quality_thresholds(poetry_like, genre="maqamat_saj")
    assert not passes_quality_thresholds(poetry_like, genre="other")
    assert not passes_quality_thresholds(poetry_like, genre="tafsir")


def test_long_line_ratio_is_not_a_quality_gate() -> None:
    """Check usuniety z §3 — nie wraca pod nowym progiem."""
    text = "هذا كتاب في الادب والتاريخ " * 40
    metrics = replace(compute_quality_metrics(text), long_line_ratio=0.99)
    assert passes_quality_thresholds(metrics, genre="adab_prose")
