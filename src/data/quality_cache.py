"""Cache metryk jakosci OpenITI — pobranie tekstu, policzenie, wyrzucenie tresci.

HTTP != 200 albo wyjatek sieciowy = rekord z http_ok=false. Nie zgadujemy metryk.
Cache jest wznowialny (jsonl po version_uri).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any

import pandas as pd
import requests

from src.data.download_openiti import raw_text_url
from src.data.quality_proxy import compute_quality_metrics
from src.paths import DATA_INTERIM_DIR
from src.utils.io import append_jsonl, ensure_dir, read_jsonl
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)

QUALITY_CACHE_PATH: Path = DATA_INTERIM_DIR / "openiti_quality_metrics.jsonl"
DEFAULT_WORKERS = 8
DEFAULT_TIMEOUT = 90


def load_quality_cache(path: Path = QUALITY_CACHE_PATH) -> dict[str, dict[str, Any]]:
    by_uri: dict[str, dict[str, Any]] = {}
    for record in read_jsonl(path):
        uri = str(record.get("version_uri") or "")
        if uri:
            by_uri[uri] = record
    return by_uri


def fetch_text_bytes(url: str, *, timeout: int = DEFAULT_TIMEOUT) -> tuple[int, bytes | None, str]:
    try:
        resp = requests.get(url, timeout=timeout)
    except requests.RequestException as exc:
        return 0, None, str(exc)
    if resp.status_code != 200:
        return resp.status_code, None, f"HTTP {resp.status_code}"
    return resp.status_code, resp.content, ""


def _metrics_record(row: pd.Series) -> dict[str, Any]:
    url = raw_text_url(row)
    status, blob, error = fetch_text_bytes(url)
    record: dict[str, Any] = {
        "version_uri": str(row["version_uri"]),
        "book": str(row.get("book") or ""),
        "url": url,
        "http_ok": blob is not None,
        "status_code": int(status),
        "error": error,
        "n_bytes": 0,
        "non_arabic_ratio": None,
        "mean_word_length": None,
        "long_line_ratio": None,
        "n_markdown_chars_removed": None,
        "n_words": None,
    }
    if blob is None:
        return record
    metrics = compute_quality_metrics(blob.decode("utf-8", errors="replace"))
    record.update(
        {
            "n_bytes": len(blob),
            "non_arabic_ratio": metrics.non_arabic_ratio,
            "mean_word_length": metrics.mean_word_length,
            "long_line_ratio": metrics.long_line_ratio,
            "n_markdown_chars_removed": metrics.n_markdown_chars_removed,
            "n_words": metrics.n_words,
        }
    )
    return record


def collect_quality_metrics(
    pool: pd.DataFrame,
    *,
    cache_path: Path = QUALITY_CACHE_PATH,
    workers: int = DEFAULT_WORKERS,
    timeout: int = DEFAULT_TIMEOUT,
    progress_every: int = 50,
) -> dict[str, dict[str, Any]]:
    """Pobiera brakujace teksty i dopisuje metryki. Wznawia z cache."""
    _ = timeout
    cache = load_quality_cache(cache_path)
    pending = [row for _, row in pool.iterrows() if str(row["version_uri"]) not in cache]
    LOGGER.info(
        "quality cache",
        extra={"cached": len(cache), "pending": len(pending), "pool": len(pool)},
    )
    if not pending:
        return cache

    ensure_dir(cache_path.parent)
    done = 0
    write_lock = Lock()
    with ThreadPoolExecutor(max_workers=workers) as pool_exec:
        futures = {pool_exec.submit(_metrics_record, row): str(row["version_uri"]) for row in pending}
        for future in as_completed(futures):
            record = future.result()
            with write_lock:
                append_jsonl(cache_path, record)
            cache[str(record["version_uri"])] = record
            done += 1
            if done % progress_every == 0 or done == len(pending):
                LOGGER.info("quality download progress", extra={"done": done, "pending": len(pending)})
                print(f"quality {done}/{len(pending)} (+{len(cache)} cached total)", flush=True)
    return cache
