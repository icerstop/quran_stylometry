#!/bin/bash
#SBATCH --job-name=qs-tag-h1b
#SBATCH --partition=hgx
#SBATCH --account=mgr_ptstmp
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=03:00:00
#SBATCH --output=/home/%u/quran-stylometry/logs/tag_ctrl_h1b_%j.out
# H1b resume po 1066297 BrokenPipeError. Checkpoint *.done zostaje (87 par na dysku). Nie dryrun — BERT juz dzialal.

set -euo pipefail
cd "$HOME/quran-stylometry"
source "$HOME/quran-stylometry/.venv/bin/activate"
export CAMELTOOLS_DATA="$HOME/camel_data"
export HF_HOME="$HOME/.cache/huggingface"
export TRANSFORMERS_CACHE="$HOME/.cache/huggingface"
export PYTHONHASHSEED=0
mkdir -p "$HOME/quran-stylometry/logs"

python -c "from tabulate import tabulate" \
  || { echo "BLAD: w .venv brak tabulate==0.9.0 — pip install przed sbatch"; exit 1; }

TAGGED="$HOME/quran-stylometry/data/interim/ctrl_tagged"
if [ -d "$TAGGED" ]; then
  find "$TAGGED" -name '*.parquet' -print0 | while IFS= read -r -d '' f; do
    stem="${f%.parquet}"
    if [ ! -f "${stem}.done" ]; then
      rm -f "$f"
      echo "removed incomplete $f"
    fi
  done
fi

python -m src.cli tag \
  --corpus ctrl \
  --input  "$HOME/quran-stylometry/data/interim/ctrl_capped" \
  --output "$HOME/quran-stylometry/data/interim/ctrl_tagged" \
  --disambiguator bert \
  --batch-size 64 \
  --checkpoint-every 200 \
  --config configs/base.yaml
