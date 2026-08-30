# REPRODUCE.md — jak odtworzyc wyniki

Pelna instrukcja odtworzenia od zera powstaje w **T-050**. Ten plik opisuje to,
co da sie odtworzyc **dzisiaj**, czyli faze P0: srodowisko, warstwe configow,
weryfikacje zrodel i sciezke zapisu figur.

## 1. Wymagania

- Python **3.12** (`requires-python = ">=3.12,<3.13"`)
- GNU Make (Windows: `winget install --id ezwinports.make -e`)
- git
- 7-Zip, dopiero od **T-009** (Windows: `winget install --id 7zip.7zip -e`;
  Linux: `apt install p7zip-full`; macOS: `brew install sevenzip`). Nie jest
  potrzebne do P0 ani do `make verify-sources` — patrz `pyproject.toml`.

## 2. Instalacja

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows:     .venv\Scripts\activate
make setup
```

`make setup` instaluje rdzen + `[dev]` z pinowanymi wersjami i tworzy
`configs/env.local.yaml` z `host_role: laptop`. Ten plik jest poza gitem i **nie
wchodzi do `config_hash`** — dzieki temu laptop i klaster licza ten sam hash dla
tego samego configu.

Tagger (potrzebny dopiero od T-014) instaluje sie osobno, bo ciagnie torch:

```bash
make setup-nlp        # camel-tools + camel_data -i light (~19 MB)
```

## 3. Weryfikacja instalacji

```bash
make test             # 150 testow + 34 pominiete (etapy P1-P6)
make figs-smoke       # FIG-00: PNG + SVG + JSON + wpis w figures/INDEX.md
make verify-sources   # raport do results/source_check.json
```

`make test` nie dotyka sieci ani `data/` — testy uzywaja `tmp_path`
i zamockowanej warstwy HTTP.

## 4. Determinizm

Dwa elementy musza sie zgadzac, zeby przebiegi byly porownywalne:

```bash
export PYTHONHASHSEED=0        # Windows: $env:PYTHONHASHSEED = "0"
python -m src.cli hash-config  # ten sam hash na kazdej maszynie
```

Aktualny hash `configs/base.yaml`:
`38ec324929d5dbd45667268e58b99ad5841d6679f98b1887fc2603f3fa3b721e`

Losowosc idzie przez `src.utils.seed.new_rng(seed, stream)` — osobny strumien na
etap. Dolozenie nowego etapu nie przesuwa losowan w etapach juz policzonych.

## 5. Sciezka bez klastra

```bash
make test CONFIG=configs/base.yaml
python -m src.cli hash-config --overlay configs/laptop_only.yaml
```

Nakladka `laptop_only.yaml` zmienia `config_hash` — to jest zamierzone. Wybor
tej sciezki musi trafic do `PREREGISTRATION.md` (T-033).

## 6. Czego jeszcze nie da sie odtworzyc

Etapy `data`, `normalize`, `tag`, `segment`, `features`, `gates`, `main`,
`chrono`, `explore`, `figs`, `dashboard`, `audit` koncza sie kodem 2
i komunikatem wskazujacym zadanie z `docs/07_TASKS.md`. To jest zachowanie
zamierzone: cichy sukces pustego etapu bylby gorszy niz jawna porazka.

`make main` dodatkowo zawodzi dopoki `configs/frozen/` jest puste (AGENTS.md
zasada 2), a `make freeze` — dopoki nie ma `results/gates.json` policzonego na
aktualnym configu.

## 7. Zadania klastrowe

`make tag-ctrl`, `make variance-array`, `make av-train`, `make embed` sa
zablokowane, gdy `HOST_ROLE != cluster`. Sposob przekazania: `docs/11_HANDOFF.md`.
