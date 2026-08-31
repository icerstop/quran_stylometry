"""Ewaluacja CAMeL vs gold EQTB na Koranie (T-014). Nie dotyka CTRL.

Alignment: edit distance na formach powierzchniowych per ajaty
(docs/07_TASKS.md T-014), nie zip po indeksie. Referencja = EQTB
(T-010 fallback, 09_DECISIONS.md §2.2). Farasa nie jest uruchamiane.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from src.annotate.align import align_surfaces, segmentation_f1
from src.annotate.gold import GoldWord, load_gold_words
from src.annotate.tagger import CamelMLETagger, PredictedWord, SentenceTagger
from src.annotate.tagset_map import eqtb_to_coarse
from src.data.download_eqtb import INTERIM_TOKENS_PATH
from src.paths import RESULTS_DIR
from src.utils.io import write_json
from src.utils.provenance import git_state, utc_now_iso

TAGGER_EVAL_PATH: Path = RESULTS_DIR / "tagger_eval.json"

EXPECTED_N_WORDS = 77_429


def _group_by_verse(words: Sequence[GoldWord]) -> list[list[GoldWord]]:
    verses: list[list[GoldWord]] = []
    current_key: tuple[int, int] | None = None
    bucket: list[GoldWord] = []
    for word in words:
        if current_key is not None and word.verse_key != current_key:
            verses.append(bucket)
            bucket = []
        current_key = word.verse_key
        bucket.append(word)
    if bucket:
        verses.append(bucket)
    return verses


def evaluate_aligned_verse(
    gold_words: Sequence[GoldWord],
    pred_words: Sequence[PredictedWord],
) -> dict[str, Any]:
    gold_surf = [w.surface_norm for w in gold_words]
    pred_surf = [w.surface_norm for w in pred_words]
    pairs = align_surfaces(gold_surf, pred_surf)

    n_gold = len(gold_words)
    n_pred = len(pred_words)
    n_aligned = 0
    pos_fine_correct = 0
    pos_coarse_correct = 0
    lemma_scored = 0
    lemma_correct = 0
    seg_f1_sum = 0.0
    seg_scored = 0
    per_pos: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    per_coarse: dict[str, list[int]] = defaultdict(lambda: [0, 0])

    for pair in pairs:
        if pair.gold_index is None or pair.pred_index is None:
            continue
        n_aligned += 1
        gold = gold_words[pair.gold_index]
        pred = pred_words[pair.pred_index]
        gold_coarse = eqtb_to_coarse(gold.pos_stem)
        fine_hit = pred.pos_eqtb is not None and pred.pos_eqtb == gold.pos_stem
        coarse_hit = pred.pos_coarse == gold_coarse
        if fine_hit:
            pos_fine_correct += 1
        if coarse_hit:
            pos_coarse_correct += 1
        per_pos[gold.pos_stem][0] += int(fine_hit)
        per_pos[gold.pos_stem][1] += 1
        per_coarse[gold_coarse][0] += int(coarse_hit)
        per_coarse[gold_coarse][1] += 1
        if gold.lemma_norm:
            lemma_scored += 1
            if pred.lemma_norm == gold.lemma_norm:
                lemma_correct += 1
        if gold.segments_norm:
            seg_f1_sum += segmentation_f1(list(gold.segments_norm), list(pred.segments_norm))
            seg_scored += 1

    return {
        "n_gold": n_gold,
        "n_pred": n_pred,
        "n_aligned": n_aligned,
        "pos_fine_correct": pos_fine_correct,
        "pos_coarse_correct": pos_coarse_correct,
        "lemma_scored": lemma_scored,
        "lemma_correct": lemma_correct,
        "seg_f1_sum": seg_f1_sum,
        "seg_scored": seg_scored,
        "gold_coarse": [eqtb_to_coarse(w.pos_stem) for w in gold_words],
        "per_pos": dict(per_pos),
        "per_coarse": dict(per_coarse),
    }


def _merge_verse_stats(parts: Sequence[dict[str, Any]]) -> dict[str, Any]:
    n_gold = sum(p["n_gold"] for p in parts)
    n_pred = sum(p["n_pred"] for p in parts)
    n_aligned = sum(p["n_aligned"] for p in parts)
    pos_fine = sum(p["pos_fine_correct"] for p in parts)
    pos_coarse = sum(p["pos_coarse_correct"] for p in parts)
    lemma_scored = sum(p["lemma_scored"] for p in parts)
    lemma_correct = sum(p["lemma_correct"] for p in parts)
    seg_scored = sum(p["seg_scored"] for p in parts)
    seg_f1_sum = sum(p["seg_f1_sum"] for p in parts)

    per_pos: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    per_coarse: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    gold_coarse: list[str] = []
    for part in parts:
        gold_coarse.extend(part["gold_coarse"])
        for tag, (hit, total) in part["per_pos"].items():
            per_pos[tag][0] += hit
            per_pos[tag][1] += total
        for tag, (hit, total) in part["per_coarse"].items():
            per_coarse[tag][0] += hit
            per_coarse[tag][1] += total

    if gold_coarse:
        majority_tag, majority_count = Counter(gold_coarse).most_common(1)[0]
    else:
        majority_tag, majority_count = "", 0
    majority_acc = (majority_count / n_gold) if n_gold else 0.0

    def _rate(num: int, den: int) -> float:
        return float(num) / den if den else 0.0

    per_pos_acc = {
        tag: {"correct": hit, "n": total, "accuracy": _rate(hit, total)}
        for tag, (hit, total) in sorted(per_pos.items())
    }
    per_coarse_acc = {
        tag: {"correct": hit, "n": total, "accuracy": _rate(hit, total)}
        for tag, (hit, total) in sorted(per_coarse.items())
    }

    return {
        "n_gold": n_gold,
        "n_pred": n_pred,
        "n_aligned": n_aligned,
        "alignment_coverage": _rate(n_aligned, n_gold),
        "token_level_accuracy": _rate(pos_coarse, n_gold),
        "pos_accuracy": _rate(pos_fine, n_gold),
        "pos_accuracy_coarse": _rate(pos_coarse, n_gold),
        "pos_accuracy_aligned_fine": _rate(pos_fine, n_aligned),
        "pos_accuracy_aligned_coarse": _rate(pos_coarse, n_aligned),
        "lemma_accuracy": _rate(lemma_correct, lemma_scored),
        "lemma_n": lemma_scored,
        "segmentation_f1": (seg_f1_sum / seg_scored) if seg_scored else 0.0,
        "segmentation_n": seg_scored,
        "majority_baseline_coarse": majority_acc,
        "majority_baseline_tag": majority_tag,
        "per_pos": per_pos_acc,
        "per_pos_coarse": per_coarse_acc,
    }


def evaluate_gold(
    gold_words: Sequence[GoldWord],
    tagger: SentenceTagger,
    *,
    progress_every: int = 200,
) -> dict[str, Any]:
    verses = _group_by_verse(gold_words)
    parts: list[dict[str, Any]] = []
    for i, verse in enumerate(verses, start=1):
        tokens = [w.surface_norm or w.surface for w in verse]
        predicted = tagger.tag_sentence(tokens)
        parts.append(evaluate_aligned_verse(verse, predicted))
        if progress_every and i % progress_every == 0:
            print(f"tagger-eval verse {i}/{len(verses)}", flush=True)
    merged = _merge_verse_stats(parts)
    merged["n_verses"] = len(verses)
    merged["n_words"] = len(gold_words)
    return merged


def run_quran_eval(
    *,
    tagger: SentenceTagger | None = None,
    eqtb_path: Path = INTERIM_TOKENS_PATH,
    out_path: Path = TAGGER_EVAL_PATH,
    max_words: int | None = None,
    config_hash: str | None = None,
    tagger_version: str = "camel-tools-1.6.0",
    database: str = "calima-msa-r13",
    disambiguator: str = "mle",
    write_figure: bool = True,
) -> dict[str, Any]:
    if not eqtb_path.exists():
        raise FileNotFoundError(
            f"Brak {eqtb_path} — T-014 wymaga T-009 (data/interim/eqtb_tokens.parquet)."
        )
    df = pd.read_parquet(eqtb_path)
    gold = load_gold_words(df, max_words=max_words)
    backend = tagger or CamelMLETagger(database=database)
    metrics = evaluate_gold(gold, backend)

    payload: dict[str, Any] = {
        "task": "T-014",
        "scope": "quran_only",
        "ctrl_tagged": False,
        "handoff_h1_prepared": False,
        "reference_corpus": "eqtb",
        "qac_status": "fallback_active",
        "reference_note": (
            "Gold = kolumny morfologiczne EQTB (T-010 / 09_DECISIONS.md §2.2). "
            "Plik QAC nie byl pobierany."
        ),
        "tagger": {
            "backend": "camel",
            "database": database,
            "disambiguator": disambiguator,
            "version": tagger_version,
        },
        "normalizer_profile": "strict",
        "token_unit": "orthographic_word",
        "expected_n_words": EXPECTED_N_WORDS,
        "n_words": metrics["n_words"],
        "n_verses": metrics["n_verses"],
        "alignment": "needleman_wunsch_surface_edit_distance",
        "config_hash": config_hash,
        "generated_at": utc_now_iso(),
        **git_state().to_dict(),
        "metrics": {
            "token_level_accuracy": metrics["token_level_accuracy"],
            "pos_accuracy": metrics["pos_accuracy"],
            "pos_accuracy_coarse": metrics["pos_accuracy_coarse"],
            "lemma_accuracy": metrics["lemma_accuracy"],
            "segmentation_f1": metrics["segmentation_f1"],
            "alignment_coverage": metrics["alignment_coverage"],
            "majority_baseline_coarse": metrics["majority_baseline_coarse"],
            "majority_baseline_tag": metrics["majority_baseline_tag"],
        },
        "per_pos": metrics["per_pos"],
        "per_pos_coarse": metrics["per_pos_coarse"],
        "lemma_n": metrics["lemma_n"],
        "segmentation_n": metrics["segmentation_n"],
        "n_aligned": metrics["n_aligned"],
        "n_pred": metrics["n_pred"],
        "truncated": max_words is not None,
    }
    write_json(out_path, payload)

    fig_paths: list[str] = []
    if write_figure:
        from src.viz.fig39_tagger_eval import run as run_fig

        saved = run_fig(payload, config_hash=config_hash)
        fig_paths = [str(saved.png), str(saved.svg), str(saved.json)]
        payload["figure"] = {
            "fig_id": "FIG-39",
            "png": "figures/FIG-39_tagger_eval.png",
            "svg": "figures/FIG-39_tagger_eval.svg",
            "json": "figures/FIG-39_tagger_eval.json",
        }
        write_json(out_path, payload)

    payload["_fig_paths"] = fig_paths
    return payload


__all__ = [
    "TAGGER_EVAL_PATH",
    "evaluate_aligned_verse",
    "evaluate_gold",
    "run_quran_eval",
]
