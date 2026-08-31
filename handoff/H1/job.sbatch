#!/bin/bash
#SBATCH --job-name=qs-tag-ctrl
#SBATCH --partition=hgx
#SBATCH --account=<KONTO>
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=<Z_PILOTAZU>
#SBATCH --output=/home/%u/quran-stylometry/logs/tag_ctrl_%j.out
# PLACEHOLDER. Nie wysylaj tego joba, dopoki dryrun.sbatch nie zwroci pilot.slurm_time (ekstrapolacja na caly korpus ×1.5).

set -euo pipefail
cd "$HOME/quran-stylometry"
source "$HOME/quran-stylometry/.venv/bin/activate"
export CAMELTOOLS_DATA="$HOME/camel_data"
export HF_HOME="$HOME/.cache/huggingface"
export TRANSFORMERS_CACHE="$HOME/.cache/huggingface"
export PYTHONHASHSEED=0
mkdir -p "$HOME/quran-stylometry/logs"

python -m src.cli tag \
  --corpus ctrl \
  --input  "$HOME/quran-stylometry/data/interim/ctrl_capped" \
  --output "$HOME/quran-stylometry/data/interim/ctrl_tagged" \
  --disambiguator bert \
  --batch-size 64 \
  --checkpoint-every 200 \
  --config configs/base.yaml
