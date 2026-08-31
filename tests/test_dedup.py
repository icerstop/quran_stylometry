"""T-017: internal_duplication_rate, dedup, shuffle — bez pelnego korpusu."""

from __future__ import annotations

from src.data.dedup import (
    count_ngrams,
    dedup_tokens,
    duplication_stats,
    measure_corpus,
    shuffle_tokens,
)
from src.utils.seed import new_rng
from src.viz.fig06_duplication import SPEC


def test_unique_stream_has_zero_duplication() -> None:
    tokens = [f"w{i}" for i in range(30)]
    stats = duplication_stats(count_ngrams(tokens, 7))
    assert stats["internal_duplication_rate"] == 0.0
    assert stats["n_types_ge2"] == 0


def test_repeated_seven_gram_raises_rate() -> None:
    gram = ["a", "b", "c", "d", "e", "f", "g"]
    tokens = gram + ["x"] + gram
    stats = duplication_stats(count_ngrams(tokens, 7))
    assert stats["n_types_ge2"] >= 1
    assert stats["internal_duplication_rate"] > 0


def test_dedup_keeps_first_occurrence_only() -> None:
    gram = ["a", "b", "c", "d", "e", "f", "g"]
    tokens = gram + gram
    kept = dedup_tokens(tokens, 7)
    assert kept == gram
    rem = duplication_stats(count_ngrams(kept, 7))
    assert rem["n_types_ge2"] == 0


def test_shuffle_destroys_repeated_sequence() -> None:
    gram = ["a", "b", "c", "d", "e", "f", "g"]
    tokens = gram * 8
    raw = float(duplication_stats(count_ngrams(tokens, 7))["internal_duplication_rate"])
    rng = new_rng(20260830, "t017_test")
    shuffled = shuffle_tokens(tokens, rng)
    shuf = float(duplication_stats(count_ngrams(shuffled, 7))["internal_duplication_rate"])
    assert raw > shuf


def test_measure_corpus_reports_both_variants() -> None:
    units = [
        ("u1", ["a", "b", "c", "d", "e", "f", "g", "a", "b", "c", "d", "e", "f", "g"]),
        ("u2", [f"z{i}" for i in range(20)]),
    ]
    rng = new_rng(1, "t017_measure")
    out = measure_corpus(units, n=7, rng=rng, write_dedup_dir=None)
    assert out["raw"]["internal_duplication_rate"] > 0
    assert out["n_tokens_dedup"] < out["n_tokens"]
    assert "internal_duplication_rate" in out["dedup"]
    assert "internal_duplication_rate" in out["shuffle"]


def test_fig06_declares_shuffle_control() -> None:
    assert SPEC.kind == "result"
    assert SPEC.control_anchor
    assert "shuffle" in SPEC.control_anchor.lower()
