"""Paczka H1: komplet plikow, job.sbatch celowo bez --time do pilotażu."""

from __future__ import annotations

from pathlib import Path

from src.config import Config
from src.handoff.pack_h1 import pack_h1, render_job_sbatch, verify_h1


def test_job_sbatch_time_is_placeholder() -> None:
    text = render_job_sbatch()
    assert "--time=<Z_PILOTAZU>" in text
    assert "--exclusive" not in text
    assert "$SCRATCH" not in text
    assert "--account=<KONTO>" in text
    assert "$HOME/quran-stylometry/data/interim/ctrl_capped" in text
    assert "$HOME/quran-stylometry/data/interim/ctrl_tagged" in text
    assert 'CAMELTOOLS_DATA="$HOME/camel_data"' in text
    assert 'HF_HOME="$HOME/.cache/huggingface"' in text
    assert "--disambiguator bert" in text
    assert "--checkpoint-every 200" in text


def test_pack_h1_writes_required_files(tmp_path: Path) -> None:
    out = tmp_path / "H1"
    capped = tmp_path / "capped"
    capped.mkdir()
    (capped / "book_a").write_text("aa bb\n", encoding="utf-8")
    (capped / "manifest.csv").write_text(
        "author_id,book_id,tokens_after_cap\nA,b1,2\n",
        encoding="utf-8",
    )
    summary = pack_h1(Config(), out_dir=out, capped_dir=capped)
    for name in (
        "README.md",
        "job.sbatch",
        "dryrun.sbatch",
        "config.frozen.yaml",
        "inputs.manifest.json",
        "expected_outputs.json",
    ):
        assert (out / name).exists() and (out / name).stat().st_size > 0
    assert summary["approved_for_sbatch"] is False
    readme = (out / "README.md").read_text(encoding="utf-8")
    assert "Nie wysylaj" in readme or "NIE" in readme
    dry = (out / "dryrun.sbatch").read_text(encoding="utf-8")
    assert "--limit-tokens 400000" in dry
    assert "--pilot" in dry
    assert "$SCRATCH" not in dry
    assert "--account=<KONTO>" in dry
    assert "$HOME/quran-stylometry/data/interim/ctrl_tagged_pilot" in dry


def test_verify_h1_fails_while_time_placeholder(tmp_path: Path) -> None:
    out = tmp_path / "H1"
    pack_h1(Config(), out_dir=out, capped_dir=tmp_path / "empty")
    errors = verify_h1(out_dir=out, strict=True)
    assert any("Z_PILOTAZU" in e for e in errors)
