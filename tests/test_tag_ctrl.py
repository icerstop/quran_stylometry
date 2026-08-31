"""T-015 tag_ctrl: chunking, ekstrapolacja --time, checkpoint — bez GPU."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.annotate.tag_ctrl import (
    chunk_tokens,
    format_slurm_time,
    recommended_job_time,
    tag_ctrl_corpus,
    write_parquet_with_retry,
)
from src.annotate.tagger import StubTagger
from src.cli import main


def test_chunk_tokens_respects_batch_size() -> None:
    chunks = chunk_tokens(["a"] * 10, 4)
    assert [len(c) for c in chunks] == [4, 4, 2]


def test_recommended_time_applies_margin() -> None:
    rec = recommended_job_time(100.0, corpus_tokens=1_000, margin=1.5)
    assert rec["seconds_raw"] == 10.0
    assert rec["seconds_with_margin"] == 15.0
    assert rec["slurm_time"] == "00:01:00"  # min 60s


def test_format_slurm_time_hours() -> None:
    assert format_slurm_time(3750) == "01:02:30"


def test_tag_ctrl_with_stub_and_limit(tmp_path: Path) -> None:
    src = tmp_path / "capped"
    dst = tmp_path / "tagged"
    src.mkdir()
    (src / "book_a").write_text("aa bb cc dd ee ff\n", encoding="utf-8")
    (src / "book_b").write_text("gg hh ii jj\n", encoding="utf-8")
    (src / "manifest.csv").write_text(
        "author_id,book_id,tokens_after_cap\nA,b1,6\nA,b2,4\n",
        encoding="utf-8",
    )
    payload = tag_ctrl_corpus(
        tagger=StubTagger(),
        input_dir=src,
        output_dir=dst,
        batch_size=3,
        checkpoint_every=1,
        limit_tokens=6,
        disambiguator="mle",
        pilot=True,
        corpus_tokens=10,
    )
    assert payload["n_tokens"] >= 6
    assert payload["truncated"] is True
    assert (dst / "book_a.parquet").exists()
    assert (dst / "book_a.done").exists()
    assert "pos_gold" not in pd.read_parquet(dst / "book_a.parquet").columns


def test_write_parquet_succeeds_on_third_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("src.annotate.tag_ctrl.time.sleep", sleeps.append)
    n = {"c": 0}

    def flaky(self: pd.DataFrame, dest: object, *args: object, **kwargs: object) -> None:
        n["c"] += 1
        if n["c"] < 3:
            raise BrokenPipeError("lustre hiccup")
        Path(str(dest)).write_bytes(b"ok")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", flaky)
    write_parquet_with_retry(pd.DataFrame({"a": [1]}), tmp_path / "x.parquet")
    assert n["c"] == 3
    assert sleeps == [2.0, 5.0]


def test_write_parquet_raises_after_three_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("src.annotate.tag_ctrl.time.sleep", lambda _s: None)
    n = {"c": 0}

    def boom(self: pd.DataFrame, dest: object, *args: object, **kwargs: object) -> None:
        n["c"] += 1
        raise OSError("disk gone")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", boom)
    with pytest.raises(OSError, match="disk gone"):
        write_parquet_with_retry(pd.DataFrame({"a": [1]}), tmp_path / "x.parquet")
    assert n["c"] == 3


def test_cli_tag_ctrl_blocked_on_laptop(capsys: object) -> None:
    assert main(["tag", "--corpus", "ctrl"]) == 1
    err = capsys.readouterr().err  # type: ignore[attr-defined]
    assert "BLOCKED" in err
    assert "sbatch" not in err.lower() or "Nie uruchamiam sbatch" in err
