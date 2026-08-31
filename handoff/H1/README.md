# H1 — tagowanie CTRL (T-015)

**Status: WYSŁANE.** Job SLURM **1066297** RUNNING (start 2026-08-31T08:55:14,
`--time=03:00:00`, konto `mgr_ptstmp`). `approved_for_sbatch=true`,
`submitted=true`. Nie `done` — czekamy na powrot artefaktow.


## Co robi
Taguje `data/interim/ctrl_capped/` disambigatorem BERT (calima-msa-r13).
Pola wyjsciowe: `*_pred` (G1). Gold EQTB nie wchodzi do tych plikow.

## Zasoby
1× GPU (`--gres=gpu:1`), 8 CPU, 48G. Partition `hgx` jak w `docs/10_COMPUTE.md` §4.

## Czas
- `dryrun.sbatch`: `--time=02:00:00` (górny szacunek na 400000 tok. BERT).
- Job **1066297** na klastrze: `--time=03:00:00` (wysłany 2026-08-31T08:55:14).
  Szablon `job.sbatch` w repo nie jest kopia robocza na klastrze.

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
`#SBATCH --account=mgr_ptstmp` — z `handoff/slurm.yaml` (to samo
w dryrun i job; nie podmieniaj w jednym pliku recznie).
`CAMELTOOLS_DATA=$HOME/camel_data`, `HF_HOME=$HOME/.cache/huggingface`.
`--checkpoint-every 200`.

