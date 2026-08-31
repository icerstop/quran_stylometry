"""H1b: restart po padzie 1066297. Nie rusza placeholderów H1."""

from __future__ import annotations

from pathlib import Path

from src.config import Config
from src.handoff.pack_h1 import render_job_sbatch as render_h1_job
from src.handoff.pack_h1b import pack_h1b, render_job_sbatch


def test_h1b_job_has_filled_time_and_resume() -> None:
    text = render_job_sbatch()
    assert "--time=03:00:00" in text
    assert "--time=<Z_PILOTAZU>" not in text
    assert "--exclusive" not in text
    assert "$SCRATCH" not in text
    assert "--account=mgr_ptstmp" in text
    assert "tabulate" in text
    assert "removed incomplete" in text
    assert "--disambiguator bert" in text
    assert "--checkpoint-every 200" in text
    assert "ctrl_tagged" in text


def test_h1_placeholder_untouched_by_h1b() -> None:
    assert "--time=<Z_PILOTAZU>" in render_h1_job()


def test_pack_h1b_writes_files(tmp_path: Path) -> None:
    out = tmp_path / "H1b"
    summary = pack_h1b(Config(), out_dir=out)
    assert summary["approved_for_sbatch"] is True
    assert summary["job_time"] == "03:00:00"
    for name in (
        "README.md",
        "job.sbatch",
        "inputs.manifest.json",
        "expected_outputs.json",
        "status.json",
    ):
        assert (out / name).exists() and (out / name).stat().st_size > 0
    assert not (out / "dryrun.sbatch").exists()
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert "1066297" in readme
    assert "BrokenPipeError" in readme
    assert "87/965" in readme
    job = (out / "job.sbatch").read_text(encoding="utf-8")
    assert job.startswith("#!/bin/bash\n")
    assert "\r" not in job
