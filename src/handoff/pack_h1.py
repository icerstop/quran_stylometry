"""Paczka H1 (T-015). Agent przygotowuje, czlowiek zatwierdza i wysyla.

Nie ustawia ``awaiting_cluster`` — H1 nie jest zatwierdzone do sbatch
dopoki dryrun nie zwroci tokenow/s i --time nie zostanie wpisane w job.sbatch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.annotate.tag_ctrl import PILOT_TOKEN_TARGET, SAFETY_MARGIN
from src.config import Config
from src.handoff.slurm import CLUSTER_ROOT, TIME_PLACEHOLDER, load_slurm_account, slurm_header
from src.paths import CTRL_CAPPED_DIR, DATA_INTERIM_DIR, HANDOFF_DIR, REPO_ROOT
from src.utils.hashing import sha256_file
from src.utils.io import ensure_dir, write_json, write_yaml

H1_DIR: Path = HANDOFF_DIR / "H1"


def render_dryrun_sbatch() -> str:
    header = slurm_header(
        job_name="qs-tag-pilot",
        time="02:00:00",
        log_stem="tag_ctrl_pilot",
        comment=(
            f"PILOTAZ: {PILOT_TOKEN_TARGET} tokenow, BERT. "
            "Wynik: results/tagger_pilot.json (tok/s + rekomendowane --time)."
        ),
    )
    body = f"""
python -m src.cli tag \\
  --corpus ctrl \\
  --input  "{CLUSTER_ROOT}/data/interim/ctrl_capped" \\
  --output "{CLUSTER_ROOT}/data/interim/ctrl_tagged_pilot" \\
  --disambiguator bert \\
  --batch-size 64 \\
  --checkpoint-every 50 \\
  --limit-tokens {PILOT_TOKEN_TARGET} \\
  --pilot \\
  --config configs/base.yaml

echo "PILOT DONE. Odczytaj results/tagger_pilot.json -> pilot.slurm_time"
echo "Wpisz te wartosc w handoff/H1/job.sbatch jako --time. Nie ruszaj job.sbatch przed tym."
"""
    return header + body


def render_job_sbatch() -> str:
    header = slurm_header(
        job_name="qs-tag-ctrl",
        time=TIME_PLACEHOLDER,
        log_stem="tag_ctrl",
        comment=(
            "PLACEHOLDER. Nie wysylaj tego joba, dopoki dryrun.sbatch nie zwroci "
            f"pilot.slurm_time (ekstrapolacja na caly korpus ×{SAFETY_MARGIN})."
        ),
    )
    body = f"""
python -m src.cli tag \\
  --corpus ctrl \\
  --input  "{CLUSTER_ROOT}/data/interim/ctrl_capped" \\
  --output "{CLUSTER_ROOT}/data/interim/ctrl_tagged" \\
  --disambiguator bert \\
  --batch-size 64 \\
  --checkpoint-every 200 \\
  --config configs/base.yaml
"""
    return header + body


def render_readme(config_hash: str, n_files: int, n_tokens: int | None) -> str:
    tokens = "policz z manifestu po T-013b" if n_tokens is None else f"{n_tokens}"
    return f"""# H1 — tagowanie CTRL (T-015)

**Status: PACZKA DO AKCEPTACJI. Nie wysylaj `job.sbatch`.**
Najpierw `dryrun.sbatch` (pilotaż BERT na {PILOT_TOKEN_TARGET} tokenach).
Dopiero po `results/tagger_pilot.json` wpisz `pilot.slurm_time` w `job.sbatch`
jako `--time` i daj znać agentowi.

## Co robi
Taguje `data/interim/ctrl_capped/` disambigatorem BERT (calima-msa-r13).
Pola wyjsciowe: `*_pred` (G1). Gold EQTB nie wchodzi do tych plikow.

## Zasoby
1× GPU (`--gres=gpu:1`), 8 CPU, 48G. Partition `hgx` jak w `docs/10_COMPUTE.md` §4.

## Czas
- `dryrun.sbatch`: `--time=02:00:00` (górny szacunek na {PILOT_TOKEN_TARGET} tok. BERT).
- `job.sbatch`: `--time=<Z_PILOTAZU>` — **niewazny SLURM**, celowo, zeby nie
  poszlo przypadkiem przed pilotażem.

## Wejscie
- `{n_files} plikow` w `data/interim/ctrl_capped/` (~{tokens} tokenow)
- `config_hash={config_hash}`

## Wyjscie (po pelnym jobie)
- `$HOME/quran-stylometry/data/interim/ctrl_tagged/*.parquet`
- checkpoint `*.done` (sha256 wejsciowego pliku)

## Walidacja po powrocie
`make handoff-verify JOB=H1`

## Zasady
Brak `--exclusive`. Brak `--array`. Brak `$SCRATCH` (klaster PUT: `$HOME`).
`#SBATCH --account={load_slurm_account()}` — z `handoff/slurm.yaml` (to samo
w dryrun i job; nie podmieniaj w jednym pliku recznie).
`CAMELTOOLS_DATA=$HOME/camel_data`, `HF_HOME=$HOME/.cache/huggingface`.
`--checkpoint-every 200`. `--time` w job.sbatch zostaje `<Z_PILOTAZU>` do pilotażu.
"""


def _inputs_manifest(capped_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not capped_dir.is_dir():
        return entries
    for path in sorted(capped_dir.iterdir()):
        if not path.is_file():
            continue
        rel = path.as_posix()
        try:
            rel = str(path.resolve().relative_to(REPO_ROOT)).replace("\\", "/")
        except ValueError:
            rel = path.as_posix()
        entries.append(
            {
                "path": rel,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return entries


def pack_h1(
    config: Config,
    *,
    out_dir: Path = H1_DIR,
    capped_dir: Path | None = None,
) -> dict[str, Any]:
    ensure_dir(out_dir)
    config_hash = config.config_hash()
    capped = capped_dir if capped_dir is not None else CTRL_CAPPED_DIR
    inputs = _inputs_manifest(capped)
    n_tokens = None
    manifest = capped / "manifest.csv"
    if manifest.exists():
        import pandas as pd

        n_tokens = int(pd.read_csv(manifest)["tokens_after_cap"].sum())

    frozen_payload = config.hashable_payload()
    frozen_text = (
        f"# config_hash: {config_hash}\n"
        f"# NIE edytuj recznie — wygenerowane przez src.handoff.pack_h1\n"
    )
    write_yaml(out_dir / "config.frozen.yaml", frozen_payload)
    body = (out_dir / "config.frozen.yaml").read_text(encoding="utf-8")
    (out_dir / "config.frozen.yaml").write_text(frozen_text + body, encoding="utf-8")

    (out_dir / "dryrun.sbatch").write_text(render_dryrun_sbatch(), encoding="utf-8", newline="\n")
    (out_dir / "job.sbatch").write_text(render_job_sbatch(), encoding="utf-8", newline="\n")
    (out_dir / "README.md").write_text(
        render_readme(config_hash, n_files=len(inputs), n_tokens=n_tokens),
        encoding="utf-8",
        newline="\n",
    )
    write_json(
        out_dir / "inputs.manifest.json",
        {
            "job": "H1",
            "config_hash": config_hash,
            "approved_for_sbatch": False,
            "n_files": len(inputs),
            "n_tokens": n_tokens,
            "files": inputs,
        },
    )
    write_json(
        out_dir / "expected_outputs.json",
        {
            "job": "H1",
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
                },
                {
                    "path": "results/tagger_pilot.json",
                    "required_for": "dryrun",
                    "schema_keys": ["tokens_per_sec", "pilot"],
                },
            ],
        },
    )
    return {
        "out_dir": str(out_dir.as_posix()),
        "config_hash": config_hash,
        "n_input_files": len(inputs),
        "n_tokens": n_tokens,
        "approved_for_sbatch": False,
        "job_time_filled": False,
    }


def _sbatch_account(script: str) -> str | None:
    for line in script.splitlines():
        if line.startswith("#SBATCH --account="):
            return line.split("=", 1)[1].strip()
    return None


def verify_h1(*, out_dir: Path = H1_DIR, strict: bool = True) -> list[str]:
    """Kompletnosc paczki H1. Artefakty tagged/ tylko gdy --time juz wypelnione."""
    errors: list[str] = []
    required = [
        "README.md",
        "job.sbatch",
        "dryrun.sbatch",
        "config.frozen.yaml",
        "inputs.manifest.json",
        "expected_outputs.json",
    ]
    for name in required:
        path = out_dir / name
        if not path.exists() or path.stat().st_size == 0:
            errors.append(f"brak albo pusty {name}")
    job_path = out_dir / "job.sbatch"
    job = job_path.read_text(encoding="utf-8") if job_path.exists() else ""
    if "--exclusive" in job:
        errors.append("job.sbatch ma --exclusive")
    if TIME_PLACEHOLDER in job:
        errors.append(
            "job.sbatch nadal ma --time=<Z_PILOTAZU> — H1 niezatwierdzone "
            "(najpierw dryrun, potem wpisz pilot.slurm_time)"
        )
    dry_path = out_dir / "dryrun.sbatch"
    dry = dry_path.read_text(encoding="utf-8") if dry_path.exists() else ""
    combined = job + "\n" + dry
    if "$SCRATCH" in combined:
        errors.append("sbatch uzywa $SCRATCH — klaster PUT go nie ma (10_COMPUTE.md par.4, $HOME)")
    job_acct = _sbatch_account(job)
    dry_acct = _sbatch_account(dry)
    if not job_acct or not dry_acct:
        errors.append("brak #SBATCH --account w job.sbatch albo dryrun.sbatch")
    elif job_acct != dry_acct:
        errors.append(
            f"job.sbatch i dryrun.sbatch maja rozne --account ({job_acct!r} vs {dry_acct!r})"
        )
    if f"{CLUSTER_ROOT}/data/interim" not in job:
        errors.append("job.sbatch nie wskazuje $HOME/quran-stylometry/data/interim")
    if strict and TIME_PLACEHOLDER not in job:
        tagged = DATA_INTERIM_DIR / "ctrl_tagged"
        if not tagged.is_dir() or not any(tagged.glob("*.parquet")):
            errors.append("brak data/interim/ctrl_tagged/*.parquet (powrot z klastra)")
    return errors
