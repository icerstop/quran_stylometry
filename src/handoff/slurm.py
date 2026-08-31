"""Wspolny szablon SLURM dla H1/H2/H3 (docs/10_COMPUTE.md §4, 11_HANDOFF.md §3).

Klaster PUT: brak ``$SCRATCH``. Trwale: ``$HOME`` (Lustre). ``/raid`` na
hgx1/hgx2 jest lokalnym NVMe — nie uzywamy bez dowodu, ze I/O jest bottleneck.

Konto rozliczeniowe NIE jest placeholderem w kazdym ``.sbatch`` osobno —
jedno zrodlo: ``handoff/slurm.yaml`` pole ``account``. ``slurm_header``
wstawia je do kazdego skryptu (dryrun i pelny job dostaja to samo).
"""

from __future__ import annotations

from pathlib import Path

from src.paths import HANDOFF_DIR
from src.utils.io import read_yaml

CLUSTER_ROOT = "$HOME/quran-stylometry"
ACCOUNT_PLACEHOLDER = "<KONTO>"
TIME_PLACEHOLDER = "<Z_PILOTAZU>"
CAMELTOOLS_DIR = "$HOME/camel_data"
HF_CACHE = "$HOME/.cache/huggingface"
SLURM_SETTINGS_PATH: Path = HANDOFF_DIR / "slurm.yaml"


def load_slurm_account(path: Path | None = None) -> str:
    """Jedno konto dla wszystkich jobow. Brak pliku / pustka → placeholder."""
    settings = path if path is not None else SLURM_SETTINGS_PATH
    if not settings.exists():
        return ACCOUNT_PLACEHOLDER
    payload = read_yaml(settings)
    raw = payload.get("account")
    if raw is None:
        return ACCOUNT_PLACEHOLDER
    account = str(raw).strip()
    return account if account else ACCOUNT_PLACEHOLDER


def slurm_header(
    *,
    job_name: str,
    time: str,
    comment: str,
    log_stem: str,
    account: str | None = None,
) -> str:
    """Naglowek + srodowisko. ``time`` moze byc placeholderem; ``account`` z yaml."""
    acc = account if account is not None else load_slurm_account()
    return f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --partition=hgx
#SBATCH --account={acc}
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time={time}
#SBATCH --output=/home/%u/quran-stylometry/logs/{log_stem}_%j.out
# {comment}

set -euo pipefail
cd "{CLUSTER_ROOT}"
source "{CLUSTER_ROOT}/.venv/bin/activate"
export CAMELTOOLS_DATA="{CAMELTOOLS_DIR}"
export HF_HOME="{HF_CACHE}"
export TRANSFORMERS_CACHE="{HF_CACHE}"
export PYTHONHASHSEED=0
mkdir -p "{CLUSTER_ROOT}/logs"
"""
