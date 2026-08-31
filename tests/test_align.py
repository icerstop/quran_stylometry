"""Alignment T-014: edit distance na formach, nie zip po indeksie."""

from __future__ import annotations

from src.annotate.align import (
    align_surfaces,
    char_levenshtein,
    segmentation_f1,
)


def test_identical_sequences_align_one_to_one() -> None:
    pairs = align_surfaces(["a", "b", "c"], ["a", "b", "c"])
    assert [(p.gold_index, p.pred_index) for p in pairs] == [(0, 0), (1, 1), (2, 2)]
    assert all(p.is_match for p in pairs)


def test_split_token_is_not_zipped_by_index() -> None:
    """Gold ma 2 slowa, pred rozbil pierwsze na dwa — indeks 1 golda nie idzie na indeks 1 preda."""
    gold = ["bsm", "allh"]
    pred = ["b", "sm", "allh"]
    pairs = align_surfaces(gold, pred)
    matched = [p for p in pairs if p.is_match]
    # "allh" musi trafic w "allh", nie w srodkowy "sm" (co dalby zip).
    gold_allh = next(p for p in matched if p.gold_surface == "allh")
    assert gold_allh.pred_surface == "allh"
    assert gold_allh.pred_index == 2
    assert gold_allh.gold_index == 1


def test_char_typo_still_pairs_the_same_slot() -> None:
    pairs = align_surfaces(["ktab", "allh"], ["ktb", "allh"])
    assert pairs[0].is_match and pairs[1].is_match
    assert pairs[0].gold_index == 0 and pairs[0].pred_index == 0


def test_empty_pred_inserts_gold_gaps() -> None:
    pairs = align_surfaces(["a", "b"], [])
    assert [p.gold_index for p in pairs] == [0, 1]
    assert all(p.pred_index is None for p in pairs)


def test_levenshtein_known_values() -> None:
    assert char_levenshtein("kitten", "sitting") == 3
    assert char_levenshtein("", "abc") == 3
    assert char_levenshtein("abc", "abc") == 0


def test_segmentation_f1_identical_and_trivial() -> None:
    assert segmentation_f1(["b", "sm"], ["b", "sm"]) == 1.0
    assert segmentation_f1(["bsm"], ["bsm"]) == 1.0
    assert segmentation_f1(["b", "sm"], ["bsm"]) == 0.0
