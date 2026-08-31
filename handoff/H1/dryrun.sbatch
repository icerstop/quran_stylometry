#!/bin/bash
#SBATCH --job-name=qs-tag-pilot
#SBATCH --partition=hgx
#SBATCH --account=mgr_ptstmp
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH --output=/home/%u/quran-stylometry/logs/tag_ctrl_pilot_%j.out
# PILOTAZ: 400000 tokenow, BERT. Wynik: results/tagger_pilot.json (tok/s + rekomendowane --time).

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
  --output "$HOME/quran-stylometry/data/interim/ctrl_tagged_pilot" \
  --disambiguator bert \
  --batch-size 64 \
  --checkpoint-every 50 \
  --limit-tokens 400000 \
  --pilot \
  --config configs/base.yaml

echo "PILOT DONE. Odczytaj results/tagger_pilot.json -> pilot.slurm_time"
echo "Wpisz te wartosc w handoff/H1/job.sbatch jako --time. Nie ruszaj job.sbatch przed tym."
