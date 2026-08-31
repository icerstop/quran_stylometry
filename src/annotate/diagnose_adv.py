"""Diagnostyka kubełka ADV w T-014 (gold T/LOC vs CAMeL).

N(ADV)=1843 w ``results/tagger_eval.json`` — za duzo, zeby odpisac
accuracy 0.007 jako szum malej kategorii. Ten modul zlicza pomyłki
i zapisuje konkretne przypadki (lokalizacja + formy).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from src.annotate.align import align_surfaces
from src.annotate.gold import GoldWord, load_gold_words
from src.annotate.tagger import CamelMLETagger, SentenceTagger
from src.annotate.tagset_map import eqtb_to_coarse
from src.data.download_eqtb import INTERIM_TOKENS_PATH
from src.paths import RESULTS_DIR
from src.utils.io import write_json
from src.utils.seed import new_rng

ADV_DIAGNOSIS_PATH: Path = RESULTS_DIR / "tagger_adv_diagnosis.json"
SAMPLE_N = 12


def _verses_with_adv(words: list[GoldWord]) -> list[list[GoldWord]]:
    buckets: dict[tuple[int, int], list[GoldWord]] = {}
    order: list[tuple[int, int]] = []
    for word in words:
        key = word.verse_key
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(word)
    return [
        buckets[k] for k in order if any(eqtb_to_coarse(w.pos_stem) == "ADV" for w in buckets[k])
    ]


def diagnose_adv(
    *,
    tagger: SentenceTagger | None = None,
    eqtb_path: Path = INTERIM_TOKENS_PATH,
    out_path: Path = ADV_DIAGNOSIS_PATH,
    sample_n: int = SAMPLE_N,
    seed: int = 20260830,
) -> dict[str, Any]:
    df = pd.read_parquet(eqtb_path)
    gold = load_gold_words(df)
    adv_words = [w for w in gold if eqtb_to_coarse(w.pos_stem) == "ADV"]
    by_gold_pos = Counter(w.pos_stem for w in adv_words)
    verses = _verses_with_adv(gold)
    backend = tagger or CamelMLETagger()

    pred_coarse: Counter[str] = Counter()
    pred_raw: Counter[str] = Counter()
    errors: list[dict[str, Any]] = []
    n_correct = 0
    n_scored = 0

    for verse in verses:
        predicted = backend.tag_sentence([w.surface_norm or w.surface for w in verse])

        pairs = align_surfaces(
            [w.surface_norm for w in verse],
            [p.surface_norm for p in predicted],
        )
        for pair in pairs:
            if pair.gold_index is None or pair.pred_index is None:
                continue
            gold_w = verse[pair.gold_index]
            if eqtb_to_coarse(gold_w.pos_stem) != "ADV":
                continue
            pred_w = predicted[pair.pred_index]
            n_scored += 1
            pred_coarse[pred_w.pos_coarse] += 1
            pred_raw[pred_w.pos_raw or "(empty)"] += 1
            hit = pred_w.pos_coarse == "ADV"
            if hit:
                n_correct += 1
            else:
                errors.append(
                    {
                        "location": (f"{gold_w.chapter_id}:{gold_w.verse_id}:{gold_w.word_id}"),
                        "surface_norm": gold_w.surface_norm,
                        "gold_pos": gold_w.pos_stem,
                        "gold_lemma": gold_w.lemma_norm,
                        "pred_pos_raw": pred_w.pos_raw,
                        "pred_pos_eqtb": pred_w.pos_eqtb,
                        "pred_pos_coarse": pred_w.pos_coarse,
                        "pred_lemma": pred_w.lemma_norm,
                    }
                )

    rng = new_rng(seed, stream="t014_adv_errors")
    sample: list[dict[str, Any]] = []
    if errors:
        idx = rng.choice(len(errors), size=min(sample_n, len(errors)), replace=False)
        sample = [errors[int(i)] for i in sorted(int(x) for x in idx.tolist())]

    payload: dict[str, Any] = {
        "task": "T-014",
        "bucket": "ADV",
        "gold_eqtb_tags": ["T", "LOC"],
        "n_gold_adv": len(adv_words),
        "n_gold_T": int(by_gold_pos.get("T", 0)),
        "n_gold_LOC": int(by_gold_pos.get("LOC", 0)),
        "n_verses_with_adv": len(verses),
        "n_scored": n_scored,
        "n_correct_coarse": n_correct,
        "accuracy_coarse": (n_correct / n_scored) if n_scored else 0.0,
        "pred_coarse_on_gold_adv": dict(pred_coarse.most_common()),
        "pred_raw_on_gold_adv": dict(pred_raw.most_common(20)),
        "n_errors": len(errors),
        "error_sample": sample,
        "diagnosis": _classify(pred_coarse, n_scored),
    }
    write_json(out_path, payload)
    return payload


def _classify(pred_coarse: Counter[str], n_scored: int) -> str:
    if n_scored == 0:
        return "empty"
    noun = pred_coarse.get("NOUN", 0) / n_scored
    conj = pred_coarse.get("CONJ", 0) / n_scored
    prep = pred_coarse.get("PREP", 0) / n_scored
    if noun >= 0.3 and conj >= 0.3:
        return (
            "Dwie systematyczne rodziny, nie szum malej kategorii: "
            f"NOUN {noun:.2f} (يوم/عند/بين/يومئذ — EQTB T/LOC vs CAMeL noun) "
            f"i CONJ {conj:.2f} (إذ/إذا/لما — EQTB T vs CAMeL conj). "
            "Kubelek ADV istnieje po obu stronach (CAMeL `adv` → EQTB T), "
            "wiec to ziarnistosc/schemat tagsetu na klasie zamknietej, "
            f"nie brak kategorii. PREP {prep:.2f} (مع: EQTB LOC vs CAMeL prep) "
            "jest trzecim rozjazdem schematu."
        )
    top, n_top = pred_coarse.most_common(1)[0]
    share = n_top / n_scored
    if top == "NOUN" and share >= 0.5:
        return (
            "CAMeL traktuje wiekszosc gold T/LOC jako noun — to nie jest "
            "ziarnistosc tagsetu (kubelek ADV istnieje po obu stronach: "
            "CAMeL `adv` → EQTB T), tylko systematyczna slabość taggera MSA "
            "na okolicznikach koranicznych."
        )
    if top == "PART" and share >= 0.5:
        return "gold ADV schodzi do PART — mieszanka mapowania i bledu taggera"
    return f"rozproszone pomyłki, najczestszy pred coarse={top} ({share:.2f})"
