# AGENTS.md — instrukcja wejściowa dla agenta kodującego

Projekt: stylometria i authorship verification Koranu w Classical Arabic.
Ten plik czytasz pierwszy. Wszystkie decyzje projektowe są już podjęte —
`docs/09_DECISIONS.md` jest wiążący. Nie pytaj użytkownika o wybory, które tam są.

## Kolejność czytania

1. `docs/09_DECISIONS.md` — zamknięte decyzje (narzędzia, źródła, parametry). Wiążące.
2. `docs/10_COMPUTE.md` — co uruchamiasz na laptopie, co na klastrze SLURM.
2b. `docs/11_HANDOFF.md` — jak przekazujesz zadania klastrowe człowiekowi. Wiążące.
3. `docs/07_TASKS.md` — backlog T-001…T-052, ścieżka krytyczna.
4. `docs/02_DESIGN.md` — guardraile G1–G9 i reguły decyzyjne.
5. `docs/03_DATA.md`, `docs/04_FEATURES.md`, `docs/05_EXPERIMENTS.md`, `docs/06_FIGURES.md` — szczegóły.
6. `docs/08_REPO.md` — struktura i configi.
7. `docs/01_REVIEW.md` — kontekst, dlaczego plan wygląda tak a nie inaczej. Opcjonalnie.

## Zasady twarde

1. **Nie zgaduj danych.** Jeśli plik źródłowy nie ma pola, którego oczekujesz —
   zatrzymaj się, zaloguj `BLOCKER` do `results/blockers.jsonl` i przejdź do
   następnego niezależnego zadania. Nigdy nie generuj syntetycznego zastępnika
   dla danych referencyjnych (chronologia, metadane autorów, tagset).
2. **Nie licz niczego na Koranie przed T-033 (FREEZE).** `make main` ma zawodzić
   bez `configs/frozen/`.
3. **Nie mieszaj `*_gold` z `*_pred`** w żadnej macierzy porównującej Koran z
   korpusem kontrolnym (guardrail G1). Test `test_no_gold_in_crosscorpus.py`
   musi przechodzić przed każdym commitem.
4. **Nie fituj wektoryzatorów ani skalerów na czymkolwiek poza CTRL-TRAIN** (G4).
5. **Nie licz p-wartości z dystansów parowych** (G5). Permutacje po autorach i surach.
6. **Nie generuj figury bez kotwicy kontrolnej** (G9).
7. **Nie zmieniaj hiperparametrów po FREEZE** bez wpisu w `DEVIATIONS.md`.
8. **Weryfikuj liczby, nie przepisuj ich z dokumentacji.** Liczba tokenów, sur,
   ajatów — zawsze policzona programowo do `results/corpus_stats.json`.
9. **Wszystko darmowe.** Żadnych zasobów wymagających licencji LDC, subskrypcji
   ani rejestracji. Jeśli trafisz na paywall — to znaczy, że wybrałeś złe źródło;
   właściwe jest w `docs/09_DECISIONS.md`.
10. **Nie masz dostępu do klastra.** Nie uruchamiasz `sbatch`, `srun`, `ssh`,
   `scp` ani `rsync`. Nie szukasz kluczy SSH ani adresów hostów. Zadanie
   klastrowe kończysz przez `make handoff JOB=<H1|H2|H3>`, wpisujesz status
   `awaiting_cluster` do `results/runs.jsonl` i **przechodzisz na niezależną
   gałąź DAG-u** (lista w `11_HANDOFF.md §4`) — nie czekasz bezczynnie.
   Po powrocie artefaktów odblokowuje cię dopiero zielony `make handoff-verify`.

## Kiedy się zatrzymać i zapytać

Tylko w tych czterech przypadkach (wszystkie inne masz rozstrzygnięte):

- format pliku źródłowego nie zgadza się z opisem w `docs/09_DECISIONS.md` §2
  (kolumny EQTB, struktura metadanych OpenITI),
- automatyczna selekcja autorów daje < 60 autorów spełniających kryteria,
- bramka E-01 lub E-07 wypada w strefie granicznej opisanej w `docs/05_EXPERIMENTS.md`,
- zasób jest niedostępny (404, zmiana licencji).

We wszystkich innych sytuacjach: wykonaj decyzję z `docs/09_DECISIONS.md`, zaloguj
i idź dalej.

## Format raportowania postępu

Po każdym zadaniu dopisz do `results/runs.jsonl`:

```json
{"task":"T-014","status":"done|blocked|skipped","config_hash":"...",
 "git_sha":"...","artifacts":["results/tagger_eval.json"],
 "metrics":{"pos_accuracy":0.83},"note":"","host":"laptop|cluster"}
```

`status: blocked` wymaga wpisu w `results/blockers.jsonl` z polem `question`.

## Pierwsze polecenie

```bash
make setup && make verify-sources
```

`make verify-sources` sprawdza dostępność wszystkich źródeł z `09_DECISIONS.md §2`
(HTTP 200, oczekiwane kolumny, licencja) i kończy się raportem. Dopóki nie jest
zielony, nie zaczynaj T-009.
