# H1b — restart T-015 po padzie 1066297

**Status: DO WYSŁANIA.** `approved_for_sbatch=true`. `--time=03:00:00`.
Nie ruszaj `handoff/H1/` — to ślad po jobie, który poszedł.

## Co się zmieniło względem H1

Job **1066297** padł ~09:01 (start 08:55) na:

`BrokenPipeError: [Errno 108] Cannot send after transport endpoint shutdown`
przy zapisie `0309KuracNaml.MunajjadFiLugha.Shamela0036950-ara1.parquet`.

Potem atexit torch dynamo: `module 'tabulate' has no attribute 'tabulate'`
(brak pinu `tabulate==0.9.0` w venv). To nie przyczyna pada.

Stan dysku w chwili pada: **87/965** par parquet+.done.
Kod w `0309KuracNaml.MunajjadFiLugha.Shamela0036950-ara1.done` nie powstał — niepełny parquet H1b usuwa przed startem.

Poprawki już w `ebcb763` (i ten SHA):
- `write_parquet_with_retry` (3 próby, sleep 2s/5s) na `OSError`/`BrokenPipeError`
- pin `tabulate==0.9.0` w extras `[nlp]`

Resume: `tag_ctrl_corpus` pomija plik gdy `{name}.done` i `{name}.parquet`
istnieją i sha256 w `.done` zgadza się z wejściem. Nie taguje od zera.

## Zasoby
Jak H1: 1× GPU, 8 CPU, 48G, partition `hgx`, `--account=mgr_ptstmp`.
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
- `$HOME/quran-stylometry/data/interim/ctrl_tagged/*.parquet` (cel: 965)
- `logs/tag_ctrl_h1b_<jobid>.out`

## Walidacja po powrocie
`make handoff-verify JOB=H1`

`config_hash=fc128adbe1eecbc0c3f6e38a5f39d03e90feb83e1bdcbd965b1ecc72553ed2db`
