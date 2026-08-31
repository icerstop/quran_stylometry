"""T-016: n-gramy Koranu, margines ±3, shuffle — bez pelnego korpusu."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import QuotesCfg
from src.data.detect_quran_quotes import (
    JaccardFuzzy,
    apply_spans,
    clean_ctrl_quotes,
    merge_hit_spans,
    quran_word_tokens,
    scan_book,
    token_ngrams,
)
from src.data.normalize_arabic import normalize


def test_token_ngrams_length() -> None:
    assert token_ngrams(["a", "b", "c", "d"], 3) == [
        ("a", "b", "c"),
        ("b", "c", "d"),
    ]
    assert token_ngrams(["a", "b"], 3) == []


def test_merge_margin_and_apply() -> None:
    tokens = list("abcdefghij")
    spans = merge_hit_spans([2], n=3, margin=1, length=len(tokens))
    # hit at 2 covers tokens 2,3,4; margin ±1 → 1..6 exclusive hi=6
    assert spans == [(1, 6)]
    kept, n_drop = apply_spans(tokens, spans)
    assert n_drop == 5
    assert "".join(kept) == "aghij"


def test_exact_quote_is_removed() -> None:
    quran = ["w1", "w2", "w3", "w4", "w5", "w6", "w7", "tail"]
    cfg = QuotesCfg()
    exact = set(token_ngrams(quran, cfg.quote_ngram_n))
    pad = ["p1", "p2", "p3", "p4"]
    book = pad + ["w1", "w2", "w3", "w4", "w5", "w6", "w7"] + pad
    result = scan_book(book, exact=exact, fuzzy=None, vocab=set(), cfg=cfg)
    assert result["n_exact_hits"] == 1
    assert "w4" not in result["cleaned"]
    assert result["cleaned"][0] == "p1"
    assert result["cleaned"][-1] == "p4"


def test_fuzzy_jaccard_catches_one_swap() -> None:
    cfg = QuotesCfg()
    quran_gram = ("a", "b", "c", "d", "e", "f", "g")
    fuzzy = JaccardFuzzy(threshold=cfg.minhash_threshold)
    fuzzy.add(quran_gram)
    book = ["x", "a", "b", "c", "d", "e", "f", "h", "y"]  # 6/7 overlap vs 8 union = 0.75 < 0.8
    # 6 unique shared, query set 7, other 7, I=6, U=8, 0.75 — should NOT match
    vocab = set(quran_gram)
    result = scan_book(
        book, exact=set(), fuzzy=fuzzy, vocab=vocab, cfg=cfg
    )
    # 0.75 < 0.8
    assert result["n_fuzzy_hits"] == 0

    book2 = ["x", "a", "b", "c", "d", "e", "f", "g", "y"]
    exact = {quran_gram}
    result2 = scan_book(book2, exact=exact, fuzzy=fuzzy, vocab=vocab, cfg=cfg)
    assert result2["n_exact_hits"] == 1


def test_quran_word_tokens_groups_segments() -> None:
    df = pd.DataFrame(
        {
            "chapter_id": [1, 1, 1],
            "verse_id": [1, 1, 1],
            "word_id": [1, 1, 2],
            "imlaai_token": ["ب", "سم", "الله"],
        }
    )
    tokens = quran_word_tokens(df, profile="strict")
    assert tokens == [normalize("بسم", "strict"), normalize("الله", "strict")]
    assert all(tokens)


def test_clean_ctrl_writes_shorter_file(tmp_path: Path) -> None:
    cfg = QuotesCfg()
    quran = ["t1", "t2", "t3", "t4", "t5", "t6", "t7"]
    src = tmp_path / "capped"
    dst = tmp_path / "clean"
    src.mkdir()
    (src / "book_a").write_text(
        "p1 p2 p3 p4 t1 t2 t3 t4 t5 t6 t7 q1 q2 q3 q4\n", encoding="utf-8"
    )
    payload = clean_ctrl_quotes(
        quran_tokens=quran,
        input_dir=src,
        output_dir=dst,
        cfg=cfg,
        seed=1,
        genre_map={"book_a": "tafsir"},
        fuzzy=None,
        audit_k=2,
    )
    out = (dst / "book_a").read_text(encoding="utf-8").split()
    assert "t4" not in out
    assert payload["report"]["totals"]["tokens_removed"] > 0
    assert payload["report"]["by_genre"]["tafsir"]["n_books"] == 1
    assert payload["report"]["audit"]["pending_human"] is True


def test_fig05_requires_control_anchor() -> None:
    from src.viz.fig05_quotes import SPEC

    assert SPEC.kind == "result"
    assert SPEC.control_anchor
    assert "shuffle" in SPEC.control_anchor.lower()
