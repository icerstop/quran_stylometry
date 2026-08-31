# H1 — tagowanie CTRL (T-015)

**Status: PACZKA DO AKCEPTACJI. Nie wysylaj `job.sbatch`.**
Najpierw `dryrun.sbatch` (pilotaż BERT na 400000 tokenach).
Dopiero po `results/tagger_pilot.json` wpisz `pilot.slurm_time` w `job.sbatch`
jako `--time` i daj znać agentowi.

## Co robi
Taguje `data/interim/ctrl_capped/` disambigatorem BERT (calima-msa-r13).
Pola wyjsciowe: `*_pred` (G1). Gold EQTB nie wchodzi do tych plikow.

## Zasoby
1× GPU (`--gres=gpu:1`), 8 CPU, 48G. Partition `hgx` jak w `docs/10_COMPUTE.md` §4.

## Czas
- `dryrun.sbatch`: `--time=02:00:00` (górny szacunek na 400000 tok. BERT).
- `job.sbatch`: `--time=<Z_PILOTAZU>` — **niewazny SLURM**, celowo, zeby nie
  poszlo przypadkiem przed pilotażem.

## Wejscie
- `966 plikow` w `data/interim/ctrl_capped/` (~19680224 tokenow)
- `config_hash=fc128adbe1eecbc0c3f6e38a5f39d03e90feb83e1bdcbd965b1ecc72553ed2db`

## Wyjscie (po pelnym jobie)
- `$HOME/quran-stylometry/data/interim/ctrl_tagged/*.parquet`
- checkpoint `*.done` (sha256 wejsciowego pliku)

## Walidacja po powrocie
`make handoff-verify JOB=H1`

## Zasady
Brak `--exclusive`. Brak `--array`. Brak `$SCRATCH` (klaster PUT: `$HOME`).
`#SBATCH --account=<KONTO>` — podstaw przed sbatch (11_HANDOFF.md §3 pkt 4b).
`CAMELTOOLS_DATA=$HOME/camel_data`, `HF_HOME=$HOME/.cache/huggingface`.
`--checkpoint-every 200`. `--time` w job.sbatch zostaje `<Z_PILOTAZU>` do pilotażu.
