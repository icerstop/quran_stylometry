# 10 — Podział pracy: laptop vs klaster

Założenia sprzętowe:
- **LAPTOP** — 16 GB RAM, grafika zintegrowana (brak CUDA), dysk ≥ 60 GB wolnego.
- **KLASTER** — SLURM z partycją GPU (A100-80GB).

Zasada: na klaster idzie tylko to, co jest ograniczone przez GPU albo przez RAM
powyżej ~12 GB. Reszta zostaje lokalnie, bo iteracja lokalna jest 10× szybsza
w praktyce niż kolejka.

---

## 1. Tabela przydziału

| Zadanie | Gdzie | Wąskie gardło | Szacunek |
|---|---|---|---|
| T-001…T-008 fundament, testy, viz | **laptop** | — | — |
| T-009 EQTB (parsowanie ~133k tokenów) | **laptop** | — | < 1 min |
| T-010 QAC referencja | **laptop** | — | < 1 min |
| T-011 selekcja OpenITI (metadane → selektywne pobranie) | **laptop** | sieć, dysk 1,5–2 GB | 1–3 h |
| T-012 gatunek (regułowo) | **laptop** | — | sekundy |
| T-013 normalizacja 2–4 mln tokenów | **laptop** | CPU | 5–15 min |
| **T-014 ewaluacja taggera na Koranie** | **laptop** (MLE) | CPU, 77k słów | 10–30 min |
| **T-015 tagowanie CTRL (2–4 mln tokenów)** | **KLASTER** | GPU (BERT disambiguator) | 3–8 h na A100 |
| T-016 detekcja cytatów (7-gram + MinHash) | **laptop** | RAM ~4–6 GB | 1–2 h |
| T-017 redundancja wewnętrzna | **laptop** | — | 20 min |
| T-018 chronologia | **laptop** | plik gotowy | sekundy |
| T-019 segmentacja | **laptop** | — | 5 min |
| T-020 splity | **laptop** | — | sekundy |
| T-021 F1 char n-gram (TF-IDF 50k cech) | **laptop** | RAM ~3–4 GB | 20–40 min |
| T-022…T-026 F2, F4, F5, F6 | **laptop** (po transferze tagów) | — | 10–30 min każde |
| T-027 F7 składnia (tylko Koran) | **laptop** | — | 5 min |
| T-028 F8/F9 prozodia + baseline | **laptop** | — | 10 min |
| T-029 E-01 domain probe | **laptop** | — | 15 min |
| T-030 E-02 AA (LinearSVC na ~10k × 50k sparse) | **laptop** | RAM ~6 GB | 1–3 h |
| T-031 E-03 cross-genre AA | **laptop** | — | 1 h |
| T-032 E-04 siatka MFW × okno (12 kombinacji) | **KLASTER** (array job) | CPU × 12 | 30 min na A100-node |
| T-033 FREEZE | **laptop** | — | — |
| T-034 korpusy syntetyczne (B=200) | **laptop** | RAM ~4 GB | 30 min |
| **T-035 E-05 wynik główny** (V × 4 rodziny × ~10 korpusów × B=200) | **KLASTER** (array po rodzinach) | CPU równoległy | 1–3 h |
| T-036 symulacja szumu taggera | **laptop** | — | 30 min |
| T-037 E-05b dekompozycja | **laptop** | — | 15 min |
| **T-038 E-06 AV trening** (do 400k par) | **KLASTER** | RAM 30–60 GB | 2–5 h |
| T-039 E-07 OOD sanity | **KLASTER** (ten sam job co T-038) | — | 30 min |
| T-040 E-08 AV na Koranie (~19k par) | **laptop** | model zamrożony, mały wsad | 20 min |
| T-041 RQ6 kotwice | **laptop** (tagowanie kotwic → klaster) | — | 1 h + 30 min GPU |
| T-043…T-047 chronologia, CPD, klastrowanie | **laptop** | ~200 okien, trywialne | 2–4 h łącznie |
| **T-048 E-14 transformery** | **KLASTER** | GPU | 1–2 h |
| T-049…T-052 dashboard, raport, audyt | **laptop** | — | — |

**Podsumowanie:** klaster potrzebny w **pięciu** momentach — T-015, T-032, T-035,
T-038+T-039, T-048. Reszta lokalnie. Największa pojedyncza pozycja to tagowanie
korpusu kontrolnego.

---

## 2. Fallback: wszystko na laptopie

Jeśli klaster jest niedostępny, projekt nadal się domyka w wersji zredukowanej:

```yaml
# configs/laptop_only.yaml
corpus:
  min_authors: 60
  min_tokens_per_author: 20000     # zamiast 30000
  max_tokens_per_author: 60000     # przycięcie, ~1.2 mln tokenów łącznie
tagger:
  disambiguator: mle               # zamiast bert, CPU-only, camel_data -i light
av:
  pairs_max_per_split: 80000       # zamiast 400000
experiments:
  skip: [E-14]                      # transformery wypadają
```

Koszt: tagowanie MLE na 1,2 mln tokenów ≈ 2–4 h CPU, AV ≈ 1 h, E-05 ≈ 2 h.
Cała ścieżka krytyczna przechodzi w ~2 dni pracy laptopa.
**Utrata jakości:** mniejszy korpus → gorsza rozdzielczość percentyla (60 autorów
to nadal minimum z `09_DECISIONS.md`, więc wniosek główny zostaje ważny), MLE
zamiast BERT → niższa accuracy taggera, którą i tak mierzysz w T-014 i wpisujesz
do raportu.

To jest dozwolona ścieżka, nie awaria. Wybór zapisz w `PREREGISTRATION.md`.

---

## 3. Transfer danych laptop ↔ klaster

Przenosimy **tylko artefakty**, nigdy surowe teksty w obie strony.

```
laptop → klaster:  data/interim/*_normalized/   (tekst po normalizacji)
                   configs/, src/
klaster → laptop:  data/interim/*_tagged/       (tagi, parquet)
                   data/features/<family>/      (macierze .npz)
                   models/av_*.joblib
                   results/*.json
```

Rozmiary: znormalizowany CTRL ≈ 300–600 MB, tagi ≈ 1–2 GB w parquet ze
snappy, macierze cech ≈ 200–400 MB. `rsync -avz --partial`.

**Ważne:** klucz cache macierzy cech zawiera `normalizer_version` i
`tagger_version` (`08_REPO.md §1`), więc przypadkowe przemieszanie artefaktów
z dwóch środowisk jest wykrywalne, a nie ciche.

---

## 4. Skrypty SLURM

`slurm/tag_ctrl.sbatch` — T-015, największy job:

```bash
#!/bin/bash
#SBATCH --job-name=qs-tag-ctrl
#SBATCH --partition=hgx
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=10:00:00
#SBATCH --output=logs/tag_ctrl_%j.out

set -euo pipefail
source "$PROJECT/.venv/bin/activate"
export CAMELTOOLS_DATA="$SCRATCH/camel_data"
export PYTHONHASHSEED=0

python -m src.cli tag \
  --corpus ctrl \
  --input  "$SCRATCH/qs/data/interim/openiti_clean" \
  --output "$SCRATCH/qs/data/interim/ctrl_tagged" \
  --disambiguator bert \
  --batch-size 64 \
  --checkpoint-every 200 \
  --config configs/base.yaml
```

`--checkpoint-every` jest obowiązkowy: job na 10 h, który pada w 9. godzinie bez
checkpointów, kosztuje dzień. Wznowienie musi wykrywać już przetworzone pliki
po hashu wejścia.

`slurm/variance_array.sbatch` — T-035, wynik główny jako array po rodzinach cech:

```bash
#!/bin/bash
#SBATCH --job-name=qs-variance
#SBATCH --partition=cpu
#SBATCH --array=0-3
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=logs/variance_%A_%a.out

set -euo pipefail
source "$PROJECT/.venv/bin/activate"
FAMILIES=(character functional lexical baseline_lit)
python -m src.cli variance \
  --family "${FAMILIES[$SLURM_ARRAY_TASK_ID]}" \
  --bootstrap 200 \
  --config configs/frozen/base.yaml \
  --out "results/variance_${FAMILIES[$SLURM_ARRAY_TASK_ID]}.json"
```

`slurm/av_train.sbatch` — T-038 + T-039 w jednym jobie, żeby bramka OOD
wykonała się na tym samym zamrożonym modelu:

```bash
#!/bin/bash
#SBATCH --job-name=qs-av
#SBATCH --partition=cpu
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=08:00:00
#SBATCH --output=logs/av_%j.out

set -euo pipefail
source "$PROJECT/.venv/bin/activate"
python -m src.cli av-train    --config configs/frozen/base.yaml
python -m src.cli av-calibrate --config configs/frozen/base.yaml
python -m src.cli av-ood-gate  --config configs/frozen/base.yaml \
                               --out results/gates.json
```

`slurm/embeddings.sbatch` — T-048:

```bash
#!/bin/bash
#SBATCH --job-name=qs-emb
#SBATCH --partition=hgx
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=logs/emb_%j.out

set -euo pipefail
source "$PROJECT/.venv/bin/activate"
python -m src.cli embed \
  --model CAMeL-Lab/bert-base-arabic-camelbert-ca \
  --pooling mean_last4 \
  --max-length 512 \
  --batch-size 32 \
  --config configs/frozen/base.yaml
```

**Uwaga do E-14:** okna mają 400 słów ortograficznych, czyli po segmentacji
morfologicznej często > 512 subtokenów. Reguła: dziel okno na fragmenty po 512
z overlapem 64, uśrednij embeddingi fragmentów wagą liczby tokenów. Zapisz
`n_chunks` per okno — jeśli koreluje z wynikiem, to artefakt, nie sygnał.

---

## 5. Pułapki zasobowe, które wyjdą w pierwszej godzinie

1. `camel_data -i light` to 19 MB, `camel_data -i full` to **1,8 GB**. Na
   laptopie instaluj `light`, na klastrze `full` do `$SCRATCH`, nie do `$HOME`
   (limity quota).
2. Pełny release OpenITI to 2,27 mld słów. **Nigdy nie klonuj całości.**
   Najpierw metadane, potem selektywne pobranie ~80 plików.
3. `TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5))` na 4 mln tokenów
   buduje ogromny słownik przed przycięciem do `max_features`. Ustaw `min_df=5`
   **i** przetwarzaj partiami z `HashingVectorizer` jako fallback, jeśli RAM
   przekroczy 10 GB.
4. Macierz dystansów parowych dla całego CTRL (10k × 10k float64) to 800 MB —
   nie licz jej nigdy w całości. `V` liczy się na podpróbkach ~200 okien.
5. Liczba par AV rośnie kwadratowo. Twardy limit `av_pairs_max_per_split: 400000`
   z `09_DECISIONS.md §6` jest limitem, nie sugestią.
6. Na klastrze ustaw `HF_HOME` i `TRANSFORMERS_CACHE` na `$SCRATCH` — inaczej
   CAMeLBERT ląduje w `$HOME` i zapycha quotę.
