"""Wznawialne pobranie metryk jakosci dla puli T-011 (pri+ara+CLEANED+death<=900)."""

from __future__ import annotations

from src.data.download_openiti import load_metadata
from src.data.quality_cache import collect_quality_metrics
from src.data.select_ctrl import candidate_pool


def main() -> None:
    df = load_metadata()
    pool = candidate_pool(df)
    print(f"pool={len(pool)}", flush=True)
    cache = collect_quality_metrics(pool, workers=8)
    ok = sum(1 for r in cache.values() if r.get("http_ok"))
    print(f"cache_total={len(cache)} http_ok={ok}")


if __name__ == "__main__":
    main()
