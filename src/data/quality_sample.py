"""Probka jakosci OpenITI — zanim progi z §3 pojdą na caly release.

Pobiera ~60 plikow (klasyki + OCR + losowe) przez raw.githubusercontent.com,
liczy trzy metryki z `quality_proxy.py`. Deterministyczny seed z configu.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.data.download_openiti import RAW_OPENITI_DIR, load_metadata, raw_text_url
from src.data.quality_proxy import compute_quality_metrics, passes_quality_thresholds
from src.paths import RESULTS_DIR
from src.utils.io import ensure_dir, write_json
from src.utils.logging import get_logger
from src.utils.seed import new_rng

LOGGER = get_logger(__name__)

SAMPLE_DIR: Path = RAW_OPENITI_DIR / "quality_sample"
CLASSIC_NEEDLES: tuple[str, ...] = (
    "Hariri.Maqamat",
    "Hamadhani.Maqamat",
    "0354Mutanabbi.Diwan",
    "0198AbuNuwas.Diwan",
    "0256Bukhari.Sahih",
    "0261Muslim.Sahih",
    "0310Tabari.Tarikh",
    "0255Jahiz.Bayan",
    "0276IbnQutayba.Adab",
    "0505Ghazali.Ihya",
)


def _candidate_pool(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[
        df.is_pri
        & df.is_arabic
        & df.has_cleaned_tag
        & (df.death_date_ah > 0)
        & (df.death_date_ah <= 900)
    ].copy()


def _pick_by_needle(pool: pd.DataFrame, needle: str) -> pd.Series | None:
    hits = pool[pool["book"].str.contains(needle, case=False, regex=False)]
    if hits.empty:
        hits = pool[pool["book"].str.contains(needle.split(".")[-1], case=False, regex=False)]
    if hits.empty:
        return None
    # prefer smaller pri file so the probe stays cheap
    hits = hits.sort_values("tok_length_n")
    return hits.iloc[0]


def _download(url: str, dest: Path, *, timeout: int = 60) -> bytes | None:
    try:
        resp = requests.get(url, timeout=timeout)
    except requests.RequestException as exc:
        LOGGER.warning("pobranie nieudane", extra={"url": url, "error": str(exc)})
        return None
    if resp.status_code != 200:
        LOGGER.warning("HTTP nie-200", extra={"url": url, "status": resp.status_code})
        return None
    dest.write_bytes(resp.content)
    return resp.content


def run_quality_sample(
    *,
    seed: int = 20260830,
    n_random: int = 50,
    n_ocr: int = 3,
    metadata_path: Path | None = None,
) -> dict[str, Any]:
    df = load_metadata(metadata_path)
    pool = _candidate_pool(df)
    ensure_dir(SAMPLE_DIR)

    selected: list[tuple[str, pd.Series]] = []
    seen: set[str] = set()

    for needle in CLASSIC_NEEDLES:
        row = _pick_by_needle(pool, needle)
        if row is None:
            continue
        key = str(row["version_uri"])
        if key in seen:
            continue
        seen.add(key)
        selected.append(("classic", row))

    ocr_pool = pool[pool.uncorrected_ocr & ~pool["version_uri"].isin(seen)]
    ocr_pool = ocr_pool[
        (ocr_pool.tok_length_n >= 2000) & (ocr_pool.tok_length_n <= 80_000)
    ]
    rng = new_rng(seed, "openiti_quality_sample")
    if len(ocr_pool) >= n_ocr:
        idx = rng.choice(ocr_pool.index.to_numpy(), size=n_ocr, replace=False)
        for i in idx:
            row = ocr_pool.loc[i]
            seen.add(str(row["version_uri"]))
            selected.append(("ocr_flagged", row))

    rand_pool = pool[
        ~pool["version_uri"].isin(seen)
        & (pool.tok_length_n >= 2000)
        & (pool.tok_length_n <= 80_000)
    ]
    n_take = min(n_random, len(rand_pool))
    idx = rng.choice(rand_pool.index.to_numpy(), size=n_take, replace=False)
    for i in idx:
        selected.append(("random", rand_pool.loc[i]))

    rows_out: list[dict[str, Any]] = []
    for role, row in selected:
        url = raw_text_url(row)
        dest = SAMPLE_DIR / str(row["version_uri"]).replace("/", "_")
        blob = _download(url, dest)
        record: dict[str, Any] = {
            "role": role,
            "version_uri": row["version_uri"],
            "book": row["book"],
            "author_id": row["author_id"],
            "death_date_ah": float(row["death_date_ah"]),
            "tok_length_meta": float(row["tok_length_n"]) if pd.notna(row["tok_length_n"]) else None,
            "uncorrected_ocr": bool(row["uncorrected_ocr"]),
            "url": url,
            "http_ok": blob is not None,
        }
        if blob is None:
            record["skipped"] = True
            rows_out.append(record)
            continue
        metrics = compute_quality_metrics(blob.decode("utf-8", errors="replace"))
        record.update(
            {
                "n_bytes": len(blob),
                "non_arabic_ratio": metrics.non_arabic_ratio,
                "mean_word_length": metrics.mean_word_length,
                "long_line_ratio": metrics.long_line_ratio,
                "n_markdown_chars_removed": metrics.n_markdown_chars_removed,
                "passes_section3": passes_quality_thresholds(metrics),
            }
        )
        rows_out.append(record)

    table = pd.DataFrame(rows_out)
    csv_path = RESULTS_DIR / "openiti_quality_sample.csv"
    table.to_csv(csv_path, index=False)

    ok = table[table["http_ok"] == True]  # noqa: E712
    summary = {
        "n_attempted": int(len(table)),
        "n_downloaded": int(ok.shape[0]),
        "n_passed_section3": int(ok["passes_section3"].sum()) if len(ok) else 0,
        "pass_rate": float(ok["passes_section3"].mean()) if len(ok) else None,
        "by_role": {},
        "metric_quantiles": {},
        "csv": "results/openiti_quality_sample.csv",
    }
    if len(ok):
        for role, grp in ok.groupby("role"):
            summary["by_role"][str(role)] = {
                "n": int(len(grp)),
                "n_passed": int(grp["passes_section3"].sum()),
                "pass_rate": float(grp["passes_section3"].mean()),
                "non_arabic_ratio_median": float(grp["non_arabic_ratio"].median()),
                "mean_word_length_median": float(grp["mean_word_length"].median()),
                "long_line_ratio_median": float(grp["long_line_ratio"].median()),
            }
        for col in ("non_arabic_ratio", "mean_word_length", "long_line_ratio"):
            q = ok[col].quantile([0.0, 0.25, 0.5, 0.75, 1.0])
            summary["metric_quantiles"][col] = {f"p{int(k*100)}": float(v) for k, v in q.items()}

    write_json(RESULTS_DIR / "openiti_quality_sample.json", summary)
    return summary
