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
    assert "--account=mgr_ptstmp" in text
    assert "$HOME/quran-stylometry/data/interim/ctrl_capped" in text
    assert "$HOME/quran-stylometry/data/interim/ctrl_tagged" in text
    assert 'CAMELTOOLS_DATA="$HOME/camel_data"' in text
    assert 'HF_HOME="$HOME/.cache/huggingface"' in text
    assert "--disambiguator bert" in text
    assert "--checkpoint-every 200" in text


def test_dryrun_and_job_share_the_same_account() -> None:
    """Reczna podmiana w jednym sbatch nie istnieje — konto z handoff/slurm.yaml."""
    from src.handoff.pack_h1 import render_dryrun_sbatch
    from src.handoff.slurm import load_slurm_account

    account = load_slurm_account()
    assert account == "mgr_ptstmp"
    job = render_job_sbatch()
    dry = render_dryrun_sbatch()
    assert f"--account={account}" in job
    assert f"--account={account}" in dry
    job_line = next(ln for ln in job.splitlines() if ln.startswith("#SBATCH --account="))
    dry_line = next(ln for ln in dry.splitlines() if ln.startswith("#SBATCH --account="))
    assert job_line == dry_line


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
    assert "--account=mgr_ptstmp" in dry
    assert "$HOME/quran-stylometry/data/interim/ctrl_tagged_pilot" in dry


def test_slurm_account_reads_yaml(tmp_path: Path) -> None:
    from src.handoff.slurm import load_slurm_account, slurm_header

    settings = tmp_path / "slurm.yaml"
    settings.write_text("account: other_acct\n", encoding="utf-8")
    assert load_slurm_account(settings) == "other_acct"
    header = slurm_header(
        job_name="x", time="01:00:00", comment="c", log_stem="x", account="other_acct"
    )
    assert "#SBATCH --account=other_acct" in header


def test_verify_h1_rejects_mismatched_accounts(tmp_path: Path) -> None:
    out = tmp_path / "H1"
    pack_h1(Config(), out_dir=out, capped_dir=tmp_path / "empty")
    job = (out / "job.sbatch").read_text(encoding="utf-8")
    (out / "job.sbatch").write_text(
        job.replace("--account=mgr_ptstmp", "--account=INNE"), encoding="utf-8"
    )
    errors = verify_h1(out_dir=out, strict=True)
    assert any("rozne --account" in e for e in errors)


def test_verify_h1_fails_while_time_placeholder(tmp_path: Path) -> None:
    out = tmp_path / "H1"
    pack_h1(Config(), out_dir=out, capped_dir=tmp_path / "empty")
    errors = verify_h1(out_dir=out, strict=True)
    assert any("Z_PILOTAZU" in e for e in errors)


def test_verify_h1_accepts_h1b_successor_with_tagged_files(tmp_path: Path) -> None:
    import pandas as pd

    from src.handoff.pack_h1b import pack_h1b

    h1 = tmp_path / "H1"
    pack_h1(Config(), out_dir=h1, capped_dir=tmp_path / "empty")
    pack_h1b(Config(), out_dir=tmp_path / "H1b")
    capped = tmp_path / "capped"
    tagged = tmp_path / "tagged"
    capped.mkdir()
    tagged.mkdir()
    (capped / "book_a").write_text("aa bb\n", encoding="utf-8")
    (capped / "manifest.csv").write_text(
        "author_id,book_id,tokens_after_cap\nA,b1,2\n",
        encoding="utf-8",
    )
    frame = pd.DataFrame(
        {
            "token": ["aa", "bb"],
            "pos_pred": ["NOUN", "NOUN"],
            "pos_raw_pred": ["noun", "noun"],
            "lemma_pred": ["aa", "bb"],
            "morph_pred": ["aa", "bb"],
        }
    )
    frame.to_parquet(tagged / "book_a.parquet", index=False)
    (tagged / "book_a.done").write_text("x\n", encoding="utf-8")
    errors = verify_h1(out_dir=h1, strict=True, tagged_dir=tagged, capped_dir=capped)
    assert errors == []


def test_verify_tagged_rejects_gold_column(tmp_path: Path) -> None:
    import pandas as pd

    from src.handoff.pack_h1 import _verify_tagged_coverage

    capped = tmp_path / "capped"
    tagged = tmp_path / "tagged"
    capped.mkdir()
    tagged.mkdir()
    (capped / "book_a").write_text("aa\n", encoding="utf-8")
    (capped / "manifest.csv").write_text(
        "author_id,book_id,tokens_after_cap\nA,b1,1\n",
        encoding="utf-8",
    )
    pd.DataFrame(
        {
            "token": ["aa"],
            "pos_pred": ["NOUN"],
            "pos_raw_pred": ["noun"],
            "lemma_pred": ["aa"],
            "morph_pred": ["aa"],
            "pos_gold": ["NOUN"],
        }
    ).to_parquet(tagged / "book_a.parquet", index=False)
    (tagged / "book_a.done").write_text("x\n", encoding="utf-8")
    errors = _verify_tagged_coverage(tagged_dir=tagged, capped_dir=capped)
    assert any("gold" in e for e in errors)
