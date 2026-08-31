"""Paczka H1b — restart T-015 po padzie 1066297. Nie rusza handoff/H1/ (11_HANDOFF.md §7)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config import Config
from src.handoff.slurm import CLUSTER_ROOT, load_slurm_account, slurm_header
from src.paths import HANDOFF_DIR
from src.utils.io import ensure_dir, write_json

H1B_DIR: Path = HANDOFF_DIR / "H1b"
PARENT_JOBID = 1066297
N_DONE_AT_FAIL = 87
N_INPUT_BOOKS = 965
FAILED_STEM = "0309KuracNaml.MunajjadFiLugha.Shamela0036950-ara1"
JOB_TIME = "03:00:00"


def render_job_sbatch() -> str:
    header = slurm_header(
        job_name="qs-tag-h1b",
        time=JOB_TIME,
        log_stem="tag_ctrl_h1b",
        comment=(
            f"H1b resume po {PARENT_JOBID} BrokenPipeError. "
            f"Checkpoint *.done zostaje ({N_DONE_AT_FAIL} par na dysku). "
            "Nie dryrun — BERT juz dzialal."
        ),
    )
    tagged = f"{CLUSTER_ROOT}/data/interim/ctrl_tagged"
    body = f"""
python -c "from tabulate import tabulate" \\
  || {{ echo "BLAD: w .venv brak tabulate==0.9.0 — pip install przed sbatch"; exit 1; }}

TAGGED="{tagged}"
if [ -d "$TAGGED" ]; then
  find "$TAGGED" -name '*.parquet' -print0 | while IFS= read -r -d '' f; do
    stem="${{f%.parquet}}"
    if [ ! -f "${{stem}}.done" ]; then
      rm -f "$f"
      echo "removed incomplete $f"
    fi
  done
fi

python -m src.cli tag \\
  --corpus ctrl \\
  --input  "{CLUSTER_ROOT}/data/interim/ctrl_capped" \\
  --output "{tagged}" \\
  --disambiguator bert \\
  --batch-size 64 \\
  --checkpoint-every 200 \\
  --config configs/base.yaml
"""
    return header + body


def render_readme(config_hash: str) -> str:
    account = load_slurm_account()
    return f"""# H1b — restart T-015 po padzie {PARENT_JOBID}

**Status: DO WYSŁANIA.** `approved_for_sbatch=true`. `--time={JOB_TIME}`.
Nie ruszaj `handoff/H1/` — to ślad po jobie, który poszedł.

## Co się zmieniło względem H1

Job **{PARENT_JOBID}** padł ~09:01 (start 08:55) na:

`BrokenPipeError: [Errno 108] Cannot send after transport endpoint shutdown`
przy zapisie `{FAILED_STEM}.parquet`.

Potem atexit torch dynamo: `module 'tabulate' has no attribute 'tabulate'`
(brak pinu `tabulate==0.9.0` w venv). To nie przyczyna pada.

Stan dysku w chwili pada: **{N_DONE_AT_FAIL}/{N_INPUT_BOOKS}** par parquet+.done.
Kod w `{FAILED_STEM}.done` nie powstał — niepełny parquet H1b usuwa przed startem.

Poprawki już w `ebcb763` (i ten SHA):
- `write_parquet_with_retry` (3 próby, sleep 2s/5s) na `OSError`/`BrokenPipeError`
- pin `tabulate==0.9.0` w extras `[nlp]`

Resume: `tag_ctrl_corpus` pomija plik gdy `{{name}}.done` i `{{name}}.parquet`
istnieją i sha256 w `.done` zgadza się z wejściem. Nie taguje od zera.

## Zasoby
Jak H1: 1× GPU, 8 CPU, 48G, partition `hgx`, `--account={account}`.
Brak `--exclusive`. Brak `$SCRATCH`.

## Przed sbatch (na klastrze, w `.venv`)

```bash
cd ~/quran-stylometry
git pull
pip install 'tabulate==0.9.0'
sbatch handoff/H1b/job.sbatch
```

Nie odpalaj `dryrun.sbatch` — pilotaż i 87 książek już udowodniły, że BERT chodzi.
Nie nadpisuj `handoff/H1/job.sbatch`.

## Wyjście
- `$HOME/quran-stylometry/data/interim/ctrl_tagged/*.parquet` (cel: {N_INPUT_BOOKS})
- `logs/tag_ctrl_h1b_<jobid>.out`

## Walidacja po powrocie
`make handoff-verify JOB=H1`

`config_hash={config_hash}`
"""


def pack_h1b(config: Config, *, out_dir: Path = H1B_DIR) -> dict[str, Any]:
    ensure_dir(out_dir)
    config_hash = config.config_hash()
    (out_dir / "job.sbatch").write_text(render_job_sbatch(), encoding="utf-8", newline="\n")
    (out_dir / "README.md").write_text(
        render_readme(config_hash), encoding="utf-8", newline="\n"
    )
    write_json(
        out_dir / "inputs.manifest.json",
        {
            "job": "H1b",
            "parent": "H1",
            "parent_jobid": PARENT_JOBID,
            "config_hash": config_hash,
            "approved_for_sbatch": True,
            "n_done_at_fail": N_DONE_AT_FAIL,
            "n_input_books": N_INPUT_BOOKS,
            "failed_stem": FAILED_STEM,
            "parent_manifest": "handoff/H1/inputs.manifest.json",
        },
    )
    write_json(
        out_dir / "expected_outputs.json",
        {
            "job": "H1b",
            "config_hash": config_hash,
            "outputs": [
                {
                    "path": "data/interim/ctrl_tagged/",
                    "pattern": "*.parquet",
                    "schema": ["token", "pos_pred", "pos_raw_pred", "lemma_pred", "morph_pred"],
                    "forbidden_columns": [
                        "pos_gold",
                        "lemma_gold",
                        "morph_gold",
                        "deprel_gold",
                    ],
                    "validation": "n_tokens == inputs.manifest n_tokens; brak kolumn *_gold",
                }
            ],
        },
    )
    write_json(
        out_dir / "status.json",
        {
            "job": "H1b",
            "parent": "H1",
            "parent_jobid": PARENT_JOBID,
            "approved_for_sbatch": True,
            "submitted": False,
            "slurm_time": JOB_TIME,
            "task": "T-015",
            "resume": True,
        },
    )
    return {
        "out_dir": str(out_dir.as_posix()),
        "config_hash": config_hash,
        "approved_for_sbatch": True,
        "job_time": JOB_TIME,
        "parent_jobid": PARENT_JOBID,
    }
