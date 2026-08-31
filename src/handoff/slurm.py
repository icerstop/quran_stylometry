"""Wspolny szablon SLURM dla H1/H2/H3 (docs/10_COMPUTE.md §4, 11_HANDOFF.md §3).

Klaster PUT: brak ``$SCRATCH``. Trwale: ``$HOME`` (Lustre). ``/raid`` na
hgx1/hgx2 jest lokalnym NVMe — nie uzywamy bez dowodu, ze I/O jest bottleneck.
``#SBATCH --account=<KONTO>`` jest placeholderem do recznego podstawienia.
"""

from __future__ import annotations

CLUSTER_ROOT = "$HOME/quran-stylometry"
ACCOUNT_PLACEHOLDER = "<KONTO>"
TIME_PLACEHOLDER = "<Z_PILOTAZU>"
CAMELTOOLS_DIR = "$HOME/camel_data"
HF_CACHE = "$HOME/.cache/huggingface"


def slurm_header(*, job_name: str, time: str, comment: str, log_stem: str) -> str:
    """Naglowek + srodowisko. ``time`` i ``account`` moga byc placeholderami."""
    return f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --partition=hgx
#SBATCH --account={ACCOUNT_PLACEHOLDER}
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
