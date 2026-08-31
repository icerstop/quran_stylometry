"""Limit 200k tokenow per autor — alokacja proporcjonalna + losowy span."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.cap_ctrl import allocate_proportional, cap_author_books, slice_tokens, span_start
from src.utils.seed import new_rng


def test_uncapped_author_keeps_all_tokens() -> None:
    counts = [1000, 2000, 500]
    assert allocate_proportional(counts, 10_000) == counts


def test_capped_sum_equals_limit() -> None:
    counts = [80_000, 40_000, 20_000]
    out = allocate_proportional(counts, 100_000)
    assert sum(out) == 100_000
    assert all(a <= b for a, b in zip(out, counts, strict=True))
    assert out[0] > out[1] > out[2]


def test_no_positive_book_gets_zero() -> None:
    counts = [199_990, 5, 3, 2]
    out = allocate_proportional(counts, 200_000)
    assert sum(out) == 200_000
    assert all(x >= 1 for x in out)


def test_tiny_book_survives_next_to_giant() -> None:
    counts = [12_000_000, 50]
    out = allocate_proportional(counts, 200_000)
    assert out[1] >= 1
    assert out[0] + out[1] == 200_000


def test_span_is_contiguous_not_prefix_when_room() -> None:
    tokens = [f"t{i}" for i in range(100)]
    # Szukamy seeda, ktory nie startuje od 0 — algorytm nie ma prawa byc "pierwsze N".
    found_nonzero = False
    for seed in range(1, 50):
        start = span_start(100, 10, seed)
        if start != 0:
            sliced, got = slice_tokens(tokens, 10, seed)
            assert got == start
            assert sliced == tokens[start : start + 10]
            assert sliced != tokens[:10]
            found_nonzero = True
            break
    assert found_nonzero


def test_full_book_span_starts_at_zero() -> None:
    tokens = ["a", "b", "c"]
    sliced, start = slice_tokens(tokens, 3, span_seed=99)
    assert start == 0
    assert sliced == tokens


def test_cap_author_is_deterministic() -> None:
    books = [("b1", ["a"] * 80), ("b2", ["b"] * 40)]
    first = cap_author_books(books, author_id="A", limit=60, config_seed=20260830)
    second = cap_author_books(books, author_id="A", limit=60, config_seed=20260830)
    assert [m.span_seed for _, _, m in first] == [m.span_seed for _, _, m in second]
    assert [toks for _, toks, _ in first] == [toks for _, toks, _ in second]


def test_different_books_get_independent_streams() -> None:
    seed_a = int(new_rng(20260830, "ctrl_cap:A:b1").integers(0, 2**31 - 1))
    seed_b = int(new_rng(20260830, "ctrl_cap:A:b2").integers(0, 2**31 - 1))
    assert seed_a != seed_b


def test_run_ctrl_cap_writes_manifest_and_keeps_books_nonzero(tmp_path: Path) -> None:
    from src.data.cap_ctrl import run_ctrl_cap

    selected = tmp_path / "selected"
    selected.mkdir()
    (selected / "book_big").write_text(("كلمة " * 500).strip() + "\n", encoding="utf-8")
    (selected / "book_small").write_text(("حرف " * 50).strip() + "\n", encoding="utf-8")
    manifest = tmp_path / "ctrl_manifest.csv"
    pd.DataFrame(
        {
            "author_id": ["A1", "A1"],
            "book": ["big", "small"],
            "version_uri": ["book_big", "book_small"],
        }
    ).to_csv(manifest, index=False)
    out_dir = tmp_path / "capped"
    summary = run_ctrl_cap(
        limit=200,
        config_seed=20260830,
        profile="strict",
        manifest_path=manifest,
        selected_dir=selected,
        out_dir=out_dir,
        summary_path=tmp_path / "summary.json",
    )
    assert summary["n_authors_clipped"] == 1
    assert summary["tokens_after"] == 200
    assert summary["n_books_zeroed"] == 0
    assert summary["sanity_no_book_zeroed"] is True
    man = pd.read_csv(out_dir / "manifest.csv")
    assert set(man.columns) >= {
        "author_id",
        "book_id",
        "tokens_before_cap",
        "tokens_after_cap",
        "span_seed",
    }
    assert (man["tokens_after_cap"] > 0).all()
    assert (man["tokens_after_cap"] <= man["tokens_before_cap"]).all()
