"""T-020: splity po autorze, rozlacznosc, stratyfikacja, Koran zostaje target."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.config import SplitsCfg
from src.data.splits import (
    allocate_counts,
    apply_mapping_to_ctrl_parquet,
    assign_authors,
    assert_authors_disjoint,
    period_bucket,
    run_splits,
)


def _authors(*rows: tuple[str, str, int]) -> list[dict[str, object]]:
    return [
        {"author_id": aid, "genre": genre, "death_date_ah": death, "layer": None}
        for aid, genre, death in rows
    ]


def test_allocate_counts_sum_to_n() -> None:
    ratios = {"ctrl_train": 0.60, "ctrl_calib": 0.15, "ctrl_test": 0.25}
    for n in range(0, 21):
        counts = allocate_counts(n, ratios)
        assert sum(counts.values()) == n
        assert set(counts) == {"ctrl_train", "ctrl_calib", "ctrl_test"}


def test_authors_are_disjoint_across_splits() -> None:
    rows = _authors(
        *[(f"a{i:02d}", "fiqh", 300 if i < 8 else 700) for i in range(20)],
        *[(f"b{i:02d}", "tafsir", 200 if i < 5 else 800) for i in range(12)],
    )
    mapping = assign_authors(rows, ratios=SplitsCfg().model_dump(), seed=20260830)
    assert_authors_disjoint(mapping)
    assert len(mapping) == 32
    assert len(set(mapping)) == 32


def test_same_author_cannot_land_in_two_splits() -> None:
    rows = _authors(("same", "history", 250), ("other", "history", 800))
    mapping = assign_authors(rows, ratios=SplitsCfg().model_dump(), seed=1)
    assert mapping["same"] in {"ctrl_train", "ctrl_calib", "ctrl_test"}
    # duplikat w wejsciu nie dubluje autora
    mapping2 = assign_authors(rows + rows, ratios=SplitsCfg().model_dump(), seed=1)
    assert mapping2 == mapping


def test_assignment_is_deterministic() -> None:
    rows = _authors(*[(f"x{i}", "other", 400 + 10 * i) for i in range(30)])
    ratios = SplitsCfg().model_dump()
    a = assign_authors(rows, ratios=ratios, seed=20260830)
    b = assign_authors(rows, ratios=ratios, seed=20260830)
    assert a == b


def test_singleton_stratum_does_not_crash() -> None:
    rows = _authors(("only", "maqamat_saj", 250))
    mapping = assign_authors(rows, ratios=SplitsCfg().model_dump(), seed=7)
    assert mapping == {"only": "ctrl_train"}


def test_period_bucket_matches_decisions() -> None:
    assert period_bucket(500) == "near"
    assert period_bucket(501) == "broad"
    assert period_bucket(285, layer="near-period") == "near"


def test_apply_mapping_writes_split_and_leaves_quran(tmp_path: Path) -> None:
    mapping = {"authA": "ctrl_train", "authB": "ctrl_test"}
    table = pa.table(
        {
            "author_id": ["authA", "authA", "authB"],
            "split": ["ctrl_test", "ctrl_test", "ctrl_test"],
            "book_id": ["b1", "b1", "b2"],
        }
    )
    path = tmp_path / "ctrl.parquet"
    pq.write_table(table, path)
    counts = apply_mapping_to_ctrl_parquet(path, mapping)
    assert counts["ctrl_train"] == 2
    assert counts["ctrl_test"] == 1
    out = pq.read_table(path)
    splits = dict(zip(out.column("author_id").to_pylist(), out.column("split").to_pylist(), strict=True))
    assert splits["authA"] == "ctrl_train"
    assert splits["authB"] == "ctrl_test"


def test_run_splits_on_synthetic_manifest(tmp_path: Path) -> None:
    csv = tmp_path / "manifest.csv"
    csv.write_text(
        "author_id,author_genre,layer,death_date_ah\n"
        "A,fiqh,near-period,200\n"
        "A,fiqh,near-period,200\n"
        "B,fiqh,broad,700\n"
        "C,tafsir,near-period,100\n"
        "D,tafsir,broad,800\n",
        encoding="utf-8",
    )
    payload = run_splits(
        ratios=SplitsCfg().model_dump(),
        seed=20260830,
        manifest_path=csv,
        apply_windows=False,
        processed_dir=tmp_path / "processed",
    )
    assert payload["n_authors"] == 4
    assert_authors_disjoint({k: v["split"] for k, v in payload["authors"].items()})
    assert payload["windows_updated"] == []
