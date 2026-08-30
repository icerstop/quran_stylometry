# 08 — Struktura repo, konwencje, budżet

## 1. Drzewo

```text
quran-stylometry/
├── AGENTS.md                   # zasady twarde — punkt wejścia agenta (czyta go Cursor)
├── .cursor/
│   └── rules/00-project.mdc    # alwaysApply: true — skrót zasad w każdej turze
├── .gitignore
│
├── docs/                       # 00_README … 11_HANDOFF — cała dokumentacja planu
│
├── Makefile                    # setup, verify-sources, data, features, gates, freeze, main, figs, dashboard, test
├── pyproject.toml              # wersje pinowane
├── PREREGISTRATION.md          # powstaje w T-033, po tym momencie tylko do odczytu
├── DEVIATIONS.md               # każde odstępstwo po FREEZE
├── DATA_LICENSES.md
├── SOURCES.md                  # odniesienia bibliograficzne z numerami stron
├── REPRODUCE.md
│
├── handoff/                    # paczki zadań klastrowych: H1, H2, H3 (11_HANDOFF.md)
├── slurm/                      # skrypty .sbatch generowane do paczek
│
├── configs/
│   ├── base.yaml
│   ├── laptop_only.yaml        # ścieżka bez klastra (10_COMPUTE.md §2)
│   ├── env.local.yaml          # HOST_ROLE; poza gitem, agent nie przełączy na cluster
│   ├── normalizer.yaml
│   ├── features/{character,function,lexical,pos,morph,structural,syntax,prosody,baseline_lit}.yaml
│   ├── experiments/{e01..e14}.yaml
│   └── frozen/                 # snapshot configów + hashe (T-033)
│
├── data/
│   ├── raw/{eqtb,qac,openiti}/
│   ├── reference/
│   │   ├── chronologies.csv
│   │   ├── genres.csv
│   │   ├── tagset_map.csv
│   │   └── function_word_candidates.csv
│   ├── interim/
│   │   ├── ctrl_manifest.csv
│   │   ├── openiti_raw/ , openiti_clean/
│   │   └── quran_normalized/
│   ├── processed/
│   │   ├── windows_250/ , windows_400/ , windows_800/
│   │   └── synthetic/{pseudo_book,mixture_2,mixture_3,mixture_5,mixture_samegenre}/
│   └── features/<family>/<config_hash>/{matrix.npz,index.parquet,meta.json}
│
├── src/
│   ├── cli.py
│   ├── utils/{seed.py,io.py,hashing.py,logging.py,cache.py}
│   ├── data/
│   │   ├── download_eqtb.py, download_qac.py, download_openiti.py
│   │   ├── select_ctrl.py, quality_proxy.py
│   │   ├── normalize_arabic.py
│   │   ├── detect_quran_quotes.py, dedup.py
│   │   └── segment.py, splits.py, synthetic.py
│   ├── annotate/
│   │   ├── tagger.py            # jeden interfejs, backend camel|farasa
│   │   ├── evaluate_tagger.py   # vs QAC gold
│   │   └── noise_simulation.py  # T-036
│   ├── features/
│   │   ├── base.py              # fit-on-train enforcement (G4)
│   │   ├── character.py, function_words.py, lexical.py, pos.py,
│   │   │   morphology.py, structural.py, syntax.py, prosody.py, baseline_lit.py
│   │   └── embeddings.py
│   ├── distances/{delta.py,metrics.py}
│   ├── models/{attribution.py,verification.py,clustering.py,period.py,change_points.py}
│   ├── evaluation/
│   │   ├── variance.py          # V_med, V_disp, matching G6
│   │   ├── significance.py      # permutacje i bootstrap blokowy (G5)
│   │   ├── calibration.py, metrics.py
│   │   ├── leakage.py           # G1–G4 checks
│   │   └── gates.py             # E-01, E-07 decyzje
│   └── viz/
│       ├── style.py, save.py
│       └── fig01.py … fig38.py
│
├── scripts/                    # cienkie wrappery CLI, bez logiki
├── notebooks/                  # WYŁĄCZNIE eksploracja; nie wolno w nich liczyć wyników raportowanych
├── tests/
│   ├── test_normalizer.py, test_segment.py, test_no_gold_in_crosscorpus.py,
│   ├── test_fit_on_train_only.py, test_determinism.py, test_schema.py,
│   └── test_significance_blocking.py
├── figures/                    # FIG-XX.{png,svg,json} + INDEX.md
├── results/                    # *.json + runs.jsonl + gates.json + guardrail_audit.json
├── models/                     # vectorizers, AV, kalibratory (z config_hash w nazwie)
└── reports/                    # main_result.md, final_report.md, dashboard.html
```

## 2. Config — minimalny szkielet

```yaml
seed: 20260830
token_unit: orthographic_word
normalizer:
  profile: strict          # strict | light
  version: "1.0.0"
tagger:
  backend: camel           # wybrany w T-014
  version: "camel-msa-1.5.2"
segmentation:
  window_size: 400
  overlap: 0.0
  respect_boundaries: [surah_id, book_id]
  min_tail_ratio: 0.6
  max_window_ratio: 1.6
corpus:
  min_authors: 60
  min_tokens_per_author: 30000
  min_works_per_author: 2
variance:
  estimators: [med, disp]
  n_windows_match: auto     # z Koranu
  bootstrap_B: 200
  block_unit: author        # G5
significance:
  permutations: 10000
  block_unit_quran: surah_id
mfw_grid: [100, 300, 1000, 3000]
gates:
  domain_probe_auc_max: 0.98
  av_ood_eer_max: 0.35
```

## 3. Reguły kodu

- Cała logika w `src/`, testowalna bez I/O sieciowego (mockowane pobierania).
- Funkcje czyste tam, gdzie się da; stan tylko w warstwie CLI.
- Każda funkcja licząca metrykę zwraca też jej niepewność albo jawnie
  deklaruje, że jej nie ma.
- Typowanie obowiązkowe w `src/` (mypy w pre-commit).
- Żadnych ścieżek absolutnych, żadnych magicznych stałych poza configiem.
- Notebooki: tylko `01_eda.ipynb`, `02_manual_audit_quotes.ipynb`,
  `03_scratch.ipynb`. Wyniki raportowane **nigdy** nie pochodzą z notebooka.

## 4. Testy — minimum wymagane

| Test | Sprawdza |
|---|---|
| `test_normalizer.py` | idempotencja, snapshot 50 przypadków, brak utraty tokenów |
| `test_segment.py` | brak przekroczeń granic sury/dzieła, polityka krótkich sur, flagi |
| `test_no_gold_in_crosscorpus.py` | **G1** — żadna macierz cross-corpus nie zbudowana z `*_gold` |
| `test_fit_on_train_only.py` | **G4** — vectorizer nie widział Koranu ani CTRL-TEST |
| `test_significance_blocking.py` | **G5** — permutacje blokują po autorze/surze |
| `test_variance_matching.py` | **G6** — `n_w` i rozkład długości identyczne |
| `test_determinism.py` | dwa przebiegi = ten sam hash wyjścia |
| `test_schema.py` | walidacja rekordu okna |

CI: uruchamia testy + `make sample-run` na podzbiorze danych.

## 5. Budżet obliczeniowy (szacunek)

| Etap | Zasób | Szacunkowy czas |
|---|---|---|
| Pobranie + selekcja OpenITI | CPU, dysk ~30–60 GB dla pełnego release | 2–4 h |
| Normalizacja 3–4 mln tokenów | CPU | < 30 min |
| Tagowanie CTRL (CAMeL BERT disambiguator) | **GPU zalecane** | 4–12 h na GPU, dni na CPU |
| Detekcja cytatów (MinHash/LSH) | CPU, RAM ~16–32 GB | 1–3 h |
| Cechy F1–F6 | CPU | 1–2 h |
| E-05 (`V`, B=200 × 4 rodziny × ~10 korpusów) | CPU, zrównoleglone | 3–8 h |
| AV (pary, LightGBM) | CPU | 2–6 h |
| Transformery (E-14) | GPU | 1–2 h |

Masz dostęp do klastra z A100 — tagowanie CTRL i E-14 tam. Reszta lokalnie.
**Wąskie gardło to tagowanie CTRL**, nie modelowanie. Zaplanuj je wcześnie
i cache'uj agresywnie — przetagowanie 3 mln tokenów drugi raz z powodu zmiany
normalizatora kosztuje dzień.

## 6. Kolejność uruchamiania (Makefile targets)

```
make setup          # środowisko + dane camel_tools
make data           # T-009..T-012
make normalize      # T-013
make tag            # T-014, T-015   [GPU]
make clean-quotes   # T-016, T-017
make segment        # T-019, T-020
make features       # T-021..T-028
make gates          # T-029..T-032   → figures + results/gates.json
make freeze         # T-033          → PREREGISTRATION.md, configs/frozen/
make main           # T-034..T-042   → WYNIK GŁÓWNY
make chrono         # T-043..T-047
make explore        # T-048
make figs           # wszystkie figury z results/
make dashboard      # reports/dashboard.html
make audit          # T-052 guardrail audit
```

`make freeze` musi zawieść, jeśli `make gates` nie został uruchomiony
na aktualnym configu. `make main` musi zawieść bez `configs/frozen/`.
