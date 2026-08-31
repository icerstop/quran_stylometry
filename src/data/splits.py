"""T-020: splity CTRL po author_id (docs/03_DATA.md §10).

60/15/25 autorow, stratyfikacja po ``author_genre`` i epoce
(``near`` = death_date_ah <= 500, ``broad`` = 501-900). Nie po book_id
i nie po oknach. Koran zostaje ``target``.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.config import SplitsCfg
from src.paths import (
    CTRL_MANIFEST_PATH,
    DATA_PROCESSED_DIR,
    SPLITS_PATH,
    rel_to_repo,
)
from src.schemas import Split
from src.utils.io import write_json
from src.utils.seed import new_rng

SPLIT_ORDER: tuple[Split, Split, Split] = ("ctrl_train", "ctrl_calib", "ctrl_test")
NEAR_MAX_AH = 500


def period_bucket(death_date_ah: float | int | None, layer: str | None = None) -> str:
    text = str(layer or "").strip().lower()
    if text in {"near", "near-period"}:
        return "near"
    if text in {"broad", "broad-period"}:
        return "broad"
    if death_date_ah is None:
        return "na"
    try:
        death = int(float(death_date_ah))
    except (TypeError, ValueError):
        return "na"
    if death <= NEAR_MAX_AH:
        return "near"
    return "broad"


def allocate_counts(n: int, ratios: Mapping[str, float]) -> dict[str, int]:
    """Hamilton / largest remainder w kolejnosci train, calib, test."""
    if n < 0:
        raise ValueError("n nie moze byc ujemne")
    raw = [n * float(ratios[name]) for name in SPLIT_ORDER]
    floors = [int(x) for x in raw]
    rem = n - sum(floors)
    order = sorted(range(len(SPLIT_ORDER)), key=lambda i: (-(raw[i] - floors[i]), i))
    counts = floors[:]
    for k in range(rem):
        counts[order[k]] += 1
    return dict(zip(SPLIT_ORDER, counts, strict=True))


def assign_authors(
    authors: Sequence[dict[str, Any]],
    *,
    ratios: Mapping[str, float],
    seed: int,
) -> dict[str, Split]:
    """Jedna etykieta splitu na autora. Strata = (genre, period_bucket)."""
    if not authors:
        return {}
    strata: dict[tuple[str, str], list[str]] = defaultdict(list)
    seen: set[str] = set()
    for row in authors:
        aid = str(row["author_id"])
        if not aid or aid in seen:
            continue
        seen.add(aid)
        genre = str(row.get("genre") or "other")
        bucket = period_bucket(row.get("death_date_ah"), row.get("layer"))
        strata[(genre, bucket)].append(aid)

    rng = new_rng(seed, "t020_splits")
    mapping: dict[str, Split] = {}
    for key in sorted(strata):
        ids = sorted(strata[key])
        perm = rng.permutation(len(ids))
        shuffled = [ids[int(i)] for i in perm]
        counts = allocate_counts(len(shuffled), ratios)
        cursor = 0
        for split in SPLIT_ORDER:
            take = int(counts[split])
            for aid in shuffled[cursor : cursor + take]:
                mapping[aid] = split
            cursor += take
        if cursor != len(shuffled):
            raise AssertionError(f"stratum {key}: nie rozdzielono {len(shuffled)} autorow")
    return mapping


def assert_authors_disjoint(mapping: Mapping[str, str]) -> None:
    by_split: dict[str, set[str]] = defaultdict(set)
    for aid, split in mapping.items():
        by_split[str(split)].add(str(aid))
    names = list(by_split)
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            overlap = by_split[left] & by_split[right]
            if overlap:
                raise AssertionError(
                    f"autorzy w {left} i {right}: {sorted(overlap)[:8]}"
                )


def load_ctrl_authors(path: Path = CTRL_MANIFEST_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Brak {path} (T-011)")
    frame = pd.read_csv(path)
    if "author_id" not in frame.columns:
        raise ValueError(f"{path}: brak author_id")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rec in frame.to_dict("records"):
        aid = str(rec.get("author_id") or "")
        if not aid or aid in seen:
            continue
        seen.add(aid)
        death = rec.get("death_date_ah")
        try:
            death_i: int | None = int(float(death)) if death == death and death is not None else None
        except (TypeError, ValueError):
            death_i = None
        rows.append(
            {
                "author_id": aid,
                "genre": str(rec.get("author_genre") or rec.get("genre") or "other"),
                "layer": rec.get("layer"),
                "death_date_ah": death_i,
            }
        )
    return rows


def _ctrl_window_parquets(processed_dir: Path = DATA_PROCESSED_DIR) -> list[Path]:
    if not processed_dir.is_dir():
        return []
    paths: list[Path] = []
    for folder in sorted(processed_dir.glob("windows_*")):
        candidate = folder / "ctrl.parquet"
        if candidate.is_file():
            paths.append(candidate)
    return paths


def apply_mapping_to_ctrl_parquet(path: Path, mapping: Mapping[str, Split]) -> dict[str, int]:
    table = pq.read_table(path)
    if "author_id" not in table.column_names or "split" not in table.column_names:
        raise ValueError(f"{path}: potrzebne kolumny author_id i split")
    authors = [str(x) if x is not None else "" for x in table.column("author_id").to_pylist()]
    missing = sorted({a for a in authors if a not in mapping})
    if missing:
        raise KeyError(f"{path.name}: {len(missing)} autorow bez splitu, np. {missing[:5]}")
    if any(not a for a in authors):
        raise ValueError(f"{path}: puste author_id w oknie CTRL")
    new_split = [mapping[a] for a in authors]
    idx = table.schema.get_field_index("split")
    table = table.set_column(idx, "split", pa.array(new_split, type=pa.string()))
    pq.write_table(table, path)
    counts: dict[str, int] = defaultdict(int)
    for split in new_split:
        counts[str(split)] += 1
    return dict(counts)


def apply_mapping_to_windows(
    mapping: Mapping[str, Split],
    *,
    processed_dir: Path = DATA_PROCESSED_DIR,
) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    for path in _ctrl_window_parquets(processed_dir):
        counts = apply_mapping_to_ctrl_parquet(path, mapping)
        quran = path.with_name("quran.parquet")
        quran_ok = True
        if quran.is_file():
            q_splits = set(pq.read_table(quran, columns=["split"]).column("split").to_pylist())
            quran_ok = q_splits <= {"target"}
            if not quran_ok:
                raise AssertionError(f"{quran}: split Koranu nie jest target: {q_splits}")
        updated.append(
            {
                "path": rel_to_repo(path),
                "n_windows_by_split": counts,
                "quran_stays_target": quran_ok,
            }
        )
    return updated


def run_splits(
    *,
    ratios: Mapping[str, float],
    seed: int,
    manifest_path: Path = CTRL_MANIFEST_PATH,
    apply_windows: bool = True,
    processed_dir: Path = DATA_PROCESSED_DIR,
) -> dict[str, Any]:
    authors = load_ctrl_authors(manifest_path)
    mapping = assign_authors(authors, ratios=ratios, seed=seed)
    assert_authors_disjoint(mapping)
    if len(mapping) != len(authors):
        raise AssertionError(f"mapowanie {len(mapping)} != autorzy {len(authors)}")

    meta = {row["author_id"]: row for row in authors}
    by_split: dict[str, int] = {name: 0 for name in SPLIT_ORDER}
    strata_counts: dict[str, dict[str, int]] = defaultdict(lambda: {name: 0 for name in SPLIT_ORDER})
    author_payload: dict[str, Any] = {}
    for aid, split in sorted(mapping.items()):
        row = meta[aid]
        bucket = period_bucket(row.get("death_date_ah"), row.get("layer"))
        genre = str(row.get("genre") or "other")
        by_split[split] += 1
        strata_counts[f"{genre}|{bucket}"][split] += 1
        author_payload[aid] = {
            "split": split,
            "genre": genre,
            "period_bucket": bucket,
            "death_date_ah": row.get("death_date_ah"),
        }

    windows_updated: list[dict[str, Any]] = []
    if apply_windows:
        windows_updated = apply_mapping_to_windows(mapping, processed_dir=processed_dir)

    return {
        "task": "T-020",
        "seed": seed,
        "ratios": {name: float(ratios[name]) for name in SPLIT_ORDER},
        "n_authors": len(mapping),
        "n_by_split": by_split,
        "strata": dict(sorted(strata_counts.items())),
        "authors": author_payload,
        "windows_updated": windows_updated,
        "note": (
            "Split po author_id. Quran = target. G4: fit tylko ctrl_train. "
            "Wewnatrz AA dodatkowo GroupKFold(book_id) — nie w T-020."
        ),
    }


def write_splits_report(
    payload: dict[str, Any],
    *,
    path: Path = SPLITS_PATH,
    config_hash: str | None = None,
) -> Path:
    out = dict(payload)
    out["config_hash"] = config_hash
    write_json(path, out)
    return path
