"""T-015: tagowanie CTRL wybranym taggerem (pola *_pred). Uruchamiane na klastrze.

Wejscie: ``data/interim/ctrl_capped/``. Dryrun: ``--limit-tokens`` 300–500k
+ ``--pilot`` (tokeny/s → ekstrapolacja --time). Nie woła Farasy.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from src.annotate.tagger import (
    CamelMLETagger,
    PredictedWord,
    SentenceTagger,
    TaggerNotAvailableError,
    analysis_mapping,
    predicted_from_analysis,
)
from src.paths import CTRL_CAPPED_DIR, RESULTS_DIR
from src.utils.hashing import sha256_file
from src.utils.io import ensure_dir, write_json
from src.utils.provenance import utc_now_iso

PILOT_PATH: Path = RESULTS_DIR / "tagger_pilot.json"
DEFAULT_CORPUS_TOKENS = 19_680_224  # T-013b oczekiwane; nadpisywane z manifestu
SAFETY_MARGIN = 1.5
PILOT_TOKEN_TARGET = 400_000


class CamelBERTTagger:
    """BERT unfactored MSA — disambiguator klastrowy (09_DECISIONS.md §1)."""

    def __init__(self, *, database: str = "calima-msa-r13", profile: str = "strict") -> None:
        self.database = database
        self.profile = profile
        self._disambiguator: Any | None = None

    def _load(self) -> Any:
        if self._disambiguator is not None:
            return self._disambiguator
        try:
            from camel_tools.disambig.bert import BERTUnfactoredDisambiguator
        except ImportError as exc:
            raise TaggerNotAvailableError(
                "camel-tools bez BERTUnfactoredDisambiguator. "
                "Na klastrze: camel_data -i full i extras [nlp]."
            ) from exc
        try:
            self._disambiguator = BERTUnfactoredDisambiguator.pretrained()
        except Exception as exc:
            raise TaggerNotAvailableError(
                f"BERT disambiguator niedostepny ({exc}). camel_data -i full do $HOME/camel_data."
            ) from exc
        return self._disambiguator

    def tag_sentence(self, tokens: Sequence[str]) -> list[PredictedWord]:
        bert = self._load()
        words = list(tokens)
        if not words:
            return []
        disambig = bert.disambiguate(words)
        predicted: list[PredictedWord] = []
        for surface, item in zip(words, disambig, strict=True):
            analyses = getattr(item, "analyses", None) or []
            top = analyses[0] if analyses else None
            predicted.append(
                predicted_from_analysis(surface, analysis_mapping(top), profile=self.profile)
            )
        return predicted


def make_tagger(disambiguator: str, database: str = "calima-msa-r13") -> SentenceTagger:
    if disambiguator == "mle":
        return CamelMLETagger(database=database)
    if disambiguator == "bert":
        return CamelBERTTagger(database=database)
    raise ValueError(f"Nieznany disambiguator: {disambiguator!r} (mle|bert)")


def chunk_tokens(tokens: Sequence[str], batch_size: int) -> list[list[str]]:
    size = max(1, batch_size)
    return [list(tokens[i : i + size]) for i in range(0, len(tokens), size)]


def format_slurm_time(seconds: float) -> str:
    total = max(60, int(seconds + 0.5))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def recommended_job_time(
    tokens_per_sec: float,
    corpus_tokens: int = DEFAULT_CORPUS_TOKENS,
    margin: float = SAFETY_MARGIN,
) -> dict[str, Any]:
    if tokens_per_sec <= 0:
        raise ValueError("tokens_per_sec musi byc > 0")
    raw = corpus_tokens / tokens_per_sec
    with_margin = raw * margin
    return {
        "tokens_per_sec": tokens_per_sec,
        "corpus_tokens": corpus_tokens,
        "margin": margin,
        "seconds_raw": raw,
        "seconds_with_margin": with_margin,
        "slurm_time": format_slurm_time(with_margin),
    }


def _predicted_rows(tokens: Sequence[str], tagged: Sequence[PredictedWord]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for tok, pred in zip(tokens, tagged, strict=True):
        rows.append(
            {
                "token": tok,
                "pos_pred": pred.pos_coarse,
                "pos_raw_pred": pred.pos_raw,
                "lemma_pred": pred.lemma_norm,
                "morph_pred": "+".join(pred.segments_norm),
            }
        )
    return rows


def tag_ctrl_corpus(
    *,
    tagger: SentenceTagger,
    input_dir: Path = CTRL_CAPPED_DIR,
    output_dir: Path,
    batch_size: int = 64,
    checkpoint_every: int = 200,
    limit_tokens: int | None = None,
    disambiguator: str = "bert",
    config_hash: str | None = None,
    pilot: bool = False,
    corpus_tokens: int | None = None,
) -> dict[str, Any]:
    ensure_dir(output_dir)
    files = sorted(p for p in input_dir.iterdir() if p.is_file() and p.name != "manifest.csv")
    n_tokens = 0
    n_files = 0
    n_skipped = 0
    t0 = time.perf_counter()
    last_checkpoint = 0

    for path in files:
        dest = output_dir / f"{path.name}.parquet"
        done = output_dir / f"{path.name}.done"
        incoming = sha256_file(path)
        if done.exists() and dest.exists():
            recorded = done.read_text(encoding="utf-8").strip()
            if recorded == incoming:
                n_skipped += 1
                continue
        tokens = path.read_text(encoding="utf-8").split()
        if limit_tokens is not None:
            remaining = limit_tokens - n_tokens
            if remaining <= 0:
                break
            if remaining < len(tokens):
                tokens = tokens[:remaining]
        if not tokens:
            pd.DataFrame(
                columns=["token", "pos_pred", "pos_raw_pred", "lemma_pred", "morph_pred"]
            ).to_parquet(dest)
            done.write_text(incoming + "\n", encoding="utf-8")
            n_files += 1
            continue
        tagged: list[PredictedWord] = []
        for chunk in chunk_tokens(tokens, batch_size):
            tagged.extend(tagger.tag_sentence(chunk))
        pd.DataFrame(_predicted_rows(tokens, tagged)).to_parquet(dest, index=False)
        done.write_text(incoming + "\n", encoding="utf-8")
        n_files += 1
        n_tokens += len(tokens)
        if checkpoint_every and n_files - last_checkpoint >= checkpoint_every:
            last_checkpoint = n_files
            print(f"tag-ctrl checkpoint files={n_files} tokens={n_tokens}", flush=True)
        if limit_tokens is not None and n_tokens >= limit_tokens:
            break

    elapsed = time.perf_counter() - t0
    tps = (n_tokens / elapsed) if elapsed > 0 else 0.0
    payload: dict[str, Any] = {
        "task": "T-015",
        "scope": "ctrl_capped",
        "disambiguator": disambiguator,
        "n_files": n_files,
        "n_skipped_checkpoint": n_skipped,
        "n_tokens": n_tokens,
        "elapsed_sec": elapsed,
        "tokens_per_sec": tps,
        "limit_tokens": limit_tokens,
        "truncated": limit_tokens is not None and n_tokens >= (limit_tokens or 0),
        "config_hash": config_hash,
        "generated_at": utc_now_iso(),
        "gold_columns_present": False,
    }
    if pilot:
        estimate = recommended_job_time(
            tps,
            corpus_tokens=corpus_tokens or _corpus_size_from_manifest(input_dir),
        )
        payload["pilot"] = estimate
        write_json(PILOT_PATH, payload)
    return payload


def _corpus_size_from_manifest(input_dir: Path) -> int:
    manifest = input_dir / "manifest.csv"
    if not manifest.exists():
        return DEFAULT_CORPUS_TOKENS
    df = pd.read_csv(manifest)
    if "tokens_after_cap" not in df.columns:
        return DEFAULT_CORPUS_TOKENS
    return int(df["tokens_after_cap"].sum())
