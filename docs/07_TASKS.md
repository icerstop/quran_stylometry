# 07 — Backlog zadań dla agenta kodującego

Format: `T-xxx · nazwa` → **Robi:** / **DoD:** / **Pułapki:** / **Zależy od:**

Zasada nadrzędna dla agenta: **żadne zadanie nie jest ukończone bez testu
i bez zapisanego artefaktu z hashem configu.** Notebook nie jest artefaktem.

---

## P0 · Fundament (T-001 … T-008)

**T-001 · Szkielet repo i środowisko**
Robi: struktura z `08_REPO.md`, `pyproject.toml`, pinowane wersje,
`Makefile`, pre-commit (black, ruff, mypy na `src/`).
DoD: `make setup && make test` przechodzi na czystym kontenerze.
Pułapki: `camel-tools` wymaga pobrania danych (`camel_data -i light`) — ująć w Makefile.

**T-002 · Warstwa configów**
Robi: `configs/base.yaml` + `configs/experiments/*.yaml`, ładowane przez
pydantic/OmegaConf; każdy artefakt zapisywany z `config_hash` (sha256 configu).
DoD: `python -m src.cli hash-config` zwraca deterministyczny hash.
Zależy od: T-001.

**T-003 · Licencje i proweniencja danych**
Robi: `DATA_LICENSES.md` — licencja QAC, EQTB, OpenITI; wersje/DOI; data pobrania.
DoD: plik istnieje, każde źródło ma link i warunki użycia.
Pułapki: to nie jest formalność — bez tego nie opublikujesz repo.

**T-004 · Determinizm**
Robi: `src/utils/seed.py` (numpy, random, torch, sklearn), `PYTHONHASHSEED`,
`n_jobs` deterministyczne tam, gdzie ma to znaczenie.
DoD: test uruchamiający dwukrotnie ten sam pipeline i porównujący hash wyjścia.

**T-005 · Logging i rejestr przebiegów**
Robi: strukturalne logi + `results/runs.jsonl` (config_hash, git sha, czas,
metryki, ścieżki artefaktów).
DoD: każdy skrypt dopisuje wpis.

**T-006 · Cache macierzy cech**
Robi: warstwa cache po `(family, config_hash, corpus_id)`; `.npz` + `.parquet`.
DoD: drugie wywołanie nie przelicza.
Pułapki: klucz cache MUSI zawierać wersję normalizatora i taggera.

**T-007 · Kontrakty I/O**
Robi: dataclassy/pydantic dla `Window`, `FeatureMatrix`, `ExperimentResult`;
walidacja przy zapisie i odczycie.
DoD: test odrzucający rekord bez `split` lub z `n_tokens=0`.

**T-008 · Szkielet `src/viz/` + INDEX figur**
Robi: wspólny styl matplotlib, paleta, funkcja `save_fig(fig, fig_id, data)`
zapisująca PNG + SVG + JSON z danymi + wpis w `figures/INDEX.md`.
DoD: `make figs-smoke` generuje figurę testową z pełnym kompletem plików.

---

## P1 · Dane (T-009 … T-018)

**T-009 · Pobranie EQTB**
Robi: `download_quran.py` — repo `NoorBayan/Quranic`, parsowanie rozszerzonego
CoNLL-X (~43 kolumny); mapowanie kolumn do schematu w `03_DATA §9`.
DoD: DataFrame z tokenami, obiema ortografiami, morfologią, składnią; testy
liczby sur = 114 i zgodności `verse_id` z QAC.
Pułapki: **nie zakładaj z góry liczby tokenów** — policz i zapisz.

**T-010 · Pobranie QAC (referencja)**
Robi: morfologia QAC do ewaluacji taggera; mapowanie tagsetu QAC ↔ tagset
produkcyjny (tabela mapowania w `data/reference/tagset_map.csv`, ręcznie
zweryfikowana).
DoD: tabela mapowania + raport, ile tagów nie ma odpowiednika.
Pułapki: mapowanie tagsetów to najczęstsze źródło cichych błędów w tym projekcie.

**T-011 · Pobranie i selekcja OpenITI**
Robi: pobranie release z Zenodo, filtr na `PRI` + `CLEANED_VERSION`, parsowanie
metadanych YAML, selekcja ≥ 60 autorów wg kryteriów `03_DATA §2`,
proxy jakości OCR (odsetek znaków spoza zakresu, średnia długość „słowa”,
odsetek linii anomalnych).
DoD: `data/interim/ctrl_manifest.csv` z pełnymi metadanymi i flagą jakości.
Pułapki: mARkdown ma znaczniki strukturalne (`#`, `~~`, `%`, numery stron) —
usunąć, ale **policzyć, ile usunięto**.

**T-012 · Ręczna etykieta gatunku**
Robi: `genre` dla wszystkich wybranych dzieł, wg zamkniętej listy z `03_DATA §3`.
DoD: pokrycie minimalne z §3 spełnione (maqāmāt ≥ 3, poezja ≥ 5, duʿāʾ ≥ 2,
kolekcje hadisów ≥ 2). Plik `data/reference/genres.csv` z uzasadnieniem
w kolumnie `note`.
Pułapki: to zadanie wymaga człowieka lub przynajmniej weryfikacji przez człowieka.
Agent przygotowuje propozycję + listę do zatwierdzenia.

**T-013 · Normalizator arabskiego**
Robi: `normalize_arabic.py` z profilami `strict` i `light`, dokładnie wg
`03_DATA §4`.
DoD: testy idempotencji, snapshotu na 50 przypadkach brzegowych, zachowania
liczby tokenów; benchmark szybkości (musi przerobić 4 mln tokenów < 5 min).
Pułapki: kolejność operacji ma znaczenie (usuwanie diakrytyki przed czy po
ujednoliceniu alifów daje różne wyniki) — zapisać uzasadnienie kolejności.

**T-014 · Wybór i ewaluacja taggera produkcyjnego (G1) — KRYTYCZNE**
Robi: uruchomienie CAMeL Tools i Farasa na tekście koranicznym; porównanie
z QAC gold: segmentation F1, POS accuracy, lemma accuracy, per-POS breakdown.
DoD: `results/tagger_eval.json` + FIG dodatkowa; wybrany tagger zapisany
w configu jako `tagger_version`.
Pułapki: porównanie wymaga alignmentu segmentacji (różne tokenizacje) —
zaimplementować alignment przez edit distance na formach powierzchniowych,
nie „po indeksie”.

**T-015 · Anotacja obu korpusów jednym taggerem**
Robi: tagowanie Koranu i CTRL wybranym taggerem; zapis do pól `*_pred`.
DoD: 100% pokrycia, log braków; test `test_no_gold_in_crosscorpus.py`.
Zależy od: T-013, T-014.

**T-016 · Detekcja i usuwanie cytatów koranicznych**
Robi: pipeline z `03_DATA §7a` (n-gram + MinHash/LSH).
DoD: `OPENITI_CLEAN` + `quote_removal_report.json` + FIG-05 + **ręczny audyt
2×100 przypadków** z policzoną precyzją i przybliżonym recallem.
Pułapki: tafsīr może stracić 30–50% objętości — to jest poprawne, ale musi być
widoczne; rozważ oznaczenie tafsīru jako gatunku wysokiego ryzyka.

**T-017 · Redundancja wewnętrzna**
Robi: `internal_duplication_rate` per korpus + wariant `dedup=true`.
DoD: FIG-06, artefakty dla obu wariantów.

**T-018 · Tabela chronologii**
Robi: `chronologies.csv` z ≥ 3 uporządkowaniami + `composite_flag` + źródła.
DoD: FIG-06b (macierz zgodności); `SOURCES.md` z odniesieniami stronicowymi.
Pułapki: `order_sadeghi` wprowadzany ręcznie — wymaga weryfikacji przez człowieka;
jeśli nie ma dostępu do pełnego tekstu Arabica 58, zapisz to jawnie i użyj dwóch
uporządkowań, nie zmyślaj trzeciego.

---

## P2 · Segmentacja i cechy (T-019 … T-028)

**T-019 · Segmentacja na okna (G3)**
Robi: `segment.py` wg `03_DATA §6`, z flagami `composite`, `overlapping`.
DoD: assert „żadne okno nie ma > 1 `book_id`”, „żadne okno nie przekracza sury
poza kompozytowymi”; raport liczby okien per korpus; test na sztucznym wejściu.
Pułapki: sury < 250 słów — polityka musi być zaimplementowana dokładnie, nie
„jakoś”; policz, ile słów wchodzi do okien kompozytowych.

**T-020 · Splity (author-level)**
Robi: podział CTRL na TRAIN/CALIB/TEST po `author_id`, stratyfikowany po
gatunku i epoce.
DoD: test rozłączności autorów; zapis `splits.json`.

**T-021 · F1 character n-grams** · **T-022 · F2 function words** ·
**T-023 · F3 lexical** · **T-024 · F4 POS** · **T-025 · F5 morfologia** ·
**T-026 · F6 structural** · **T-027 · F7 składnia (tylko Koran)** ·
**T-028 · F8 prozodia + F9 baseline literaturowy**

Wspólne DoD dla T-021…T-028:
- vectorizer fitowany wyłącznie na CTRL-TRAIN (test automatyczny G4),
- macierz zapisana z `config_hash`, brak NaN/inf/zerowych wektorów,
- korelacja normy wektora z `n_tokens` < 0.3,
- checklist z `04_FEATURES §12` odhaczony,
- figura rozkładu top-K cech.

Pułapki per zadanie:
- T-021: `char_wb`, nie `char`; liczyć na `strict`; wariant bez diakrytyki.
- T-022: bez segmentacji morfologicznej ta rodzina jest bezwartościowa — assert.
- T-025: transformacja CLR przed metrykami euklidesowymi.
- T-026: MTLD/HD-D wrażliwe na długość — liczyć na oknach o tej samej długości.
- T-028: F8 oznaczone w metadanych jako `status: circular`; F9 wymaga
  zapisania w `SOURCES.md`, skąd wzięto listę markerów.

---

## P3 · Bramki (T-029 … T-032)

**T-029 · E-01 domain probe**
DoD: `results/domain_probe.json`, FIG-07, FIG-08; **decyzja o statusie rodzin
cech zapisana w configu**, nie tylko w raporcie.
Pułapki: probe musi obejmować też pary gatunkowe wewnątrz CTRL — bez tego
liczba dla Koranu nie ma odniesienia.

**T-030 · E-02 AA na CTRL**
DoD: FIG-09…FIG-12; `results/aa_ctrl.json`; baseline'y policzone.
Pułapki: `GroupKFold` po `book_id`, nie po oknach. MultinomialNB tylko na
nieujemnych cechach.

**T-031 · E-03 wpływ gatunku na AA**
DoD: FIG-13; liczba „spadek F1 przy zmianie gatunku” trafia do preregistration.

**T-032 · E-04 wrażliwość MFW × okno**
DoD: FIG-14.

---

## P4 · FREEZE (T-033)

**T-033 · Pre-registration i zamrożenie**
Robi: `PREREGISTRATION.md` wg `02_DESIGN §5`, `configs/frozen/` z hashami,
tag gita `freeze-v1`.
DoD: plik podpisany hashem; od tego momentu każda zmiana configu głównego
generuje wpis w `DEVIATIONS.md`.
**Zależy od:** T-029…T-032. **Blokuje:** wszystko poniżej.
Pułapki: nie wolno przed FREEZE liczyć `V_Quran` ani patrzeć na wynik główny.

---

## P5 · Wynik główny i AV (T-034 … T-042)

**T-034 · Korpusy syntetyczne PSEUDO-BOOK i MIXTURE**
Robi: generator wg `03_DATA §11`, B=200, matching `n_w` i długości (G6).
DoD: test, że `n_w` i rozkład długości są identyczne z Koranem;
`data/processed/synthetic/` z manifestem losowań i seedem.
Pułapki: MIXTURE mieszający gatunki zawyża `V` — wygenerować też
`mixture-k-samegenre`.

**T-035 · E-05 obliczenie `V` i skali odniesienia**
Robi: `V_med`, `V_disp` dla wszystkich korpusów i rodzin `core`;
percentyle z CI (bootstrap po autorach), overlapping coefficient.
DoD: FIG-15, FIG-16, FIG-17, FIG-19b; `results/variance.json`.
Pułapki: bootstrap **po autorach**, nigdy po parach (G5); ta sama skala osi
we wszystkich panelach.

**T-036 · Symulacja szumu taggera**
Robi: wstrzyknięcie błędu POS o wielkości zmierzonej w T-014 do gold-tagów
Koranu; pomiar przesunięcia `V_Quran`.
DoD: liczba „przesunięcie `V` na skutek szumu taggera” obok wyniku głównego
w FIG-16. Jeśli przesunięcie ≥ efekt — wynik oznaczony jako nieistotny.

**T-037 · E-05b dekompozycja wariancji**
DoD: FIG-18, FIG-19.

**T-038 · E-06 trening i kalibracja AV**
DoD: FIG-20…FIG-22; `results/av_ctrl.json`; hard negatives zaimplementowane
i udokumentowane (rozkład par wg gatunku/epoki/długości).
Pułapki: pary `SAME` z tego samego dzieła i z różnych dzieł raportowane osobno.

**T-039 · E-07 OOD sanity — BRAMKA**
DoD: FIG-23 + jawna decyzja `rq4_enabled: true|false` zapisana w
`results/gates.json`.
Pułapki: agent **nie ma prawa** uruchomić T-040, jeśli bramka nie przeszła.

**T-040 · E-08 AV na Koranie** (warunkowe)
DoD: FIG-24, FIG-25; test permutacyjny blokowany po surach.

**T-041 · RQ6 — kotwice zewnętrzne**
Robi: przepuszczenie dywanu, kolekcji hadisów i Nahj al-Balāgha przez cały
pipeline (`V` + AV, jeśli aktywne).
DoD: wyniki naniesione na FIG-15 i FIG-24 jako punkty odniesienia.
Pułapki: te teksty muszą przejść dokładnie ten sam pipeline, łącznie
z usuwaniem cytatów koranicznych.

**T-042 · Raport wyniku głównego**
DoD: `reports/main_result.md` napisany w formacie zdania z `00_README`
(„miara M w reprezentacji R, przy kontrolach C, plasuje Koran na percentylu P
rozkładu korpusów typu T”), dla każdej rodziny `core`, z sekcją rozbieżności.

---

## P6 · Chronologia, CPD, klastrowanie, transformery (T-043 … T-050)

**T-043 · E-09 Meccan/Medinan + baseline'y**
DoD: FIG-26, FIG-27, FIG-28; `GroupKFold` po `surah_id`; Δ wobec baseline'u
długości ajatu z CI.

**T-044 · E-10 interpretacja**
DoD: FIG-29, FIG-30; uruchamiane tylko dla modeli, które przeszły kryterium E-09.

**T-045 · E-11 change-point detection + testy negatywne**
DoD: FIG-31, FIG-32, FIG-33; penalty zamrożona przed uruchomieniem na Koranie;
warianty dla 3 uporządkowań chronologicznych i dla reszt po `mean_verse_length`.
Pułapki: panel z shuffle i mixture w tej samej figurze (G9) — nie w załączniku.

**T-046 · E-12 klastrowanie**
DoD: FIG-34, FIG-35; te same metryki policzone dla PSEUDO-BOOK i MIXTURE.

**T-047 · E-13 test „concurrent smoothness”**
DoD: FIG-36; jawna odpowiedź, czy kryterium odróżnia mieszankę od jednego autora.

**T-048 · E-14 transformery (eksploracyjne)**
DoD: FIG-37, FIG-38; adnotacja o kontaminacji na każdej figurze; osobna sekcja raportu.

**T-049 · Dashboard**
DoD: `reports/dashboard.html`, samodzielny, budowany `make dashboard`,
wszystkie liczby z `results/*.json`.

**T-050 · Raport końcowy + threats to validity**
DoD: `reports/final_report.md` z sekcjami: metoda, bramki, wynik główny,
chronologia, ograniczenia (9 pozycji z `02_DESIGN §6`, każda z liczbą),
`DEVIATIONS.md`, `REPRODUCE.md`.

**T-051 · Test odtwarzalności end-to-end**
Robi: uruchomienie całości od zera na czystym środowisku ze zredukowanym
podzbiorem danych (`sample=true`).
DoD: przechodzi w CI; czas < 30 min na podzbiorze.

**T-052 · Audyt zgodności z guardrailami**
Robi: skrypt sprawdzający G1–G9 na artefaktach końcowych.
DoD: `results/guardrail_audit.json` — wszystkie zielone albo jawnie
udokumentowane odstępstwo.

---

## Kolejność i ścieżka krytyczna

```
P0 → T-009,T-010,T-011 → T-013 → T-014 → T-015 → T-016 → T-019 → T-020
   → T-021..T-028 → T-029, T-030 → T-033 (FREEZE)
   → T-034 → T-035 (WYNIK GŁÓWNY) → T-038 → T-039 (BRAMKA) → [T-040]
   → T-043 → T-045 → T-049 → T-050
```

Zadania T-031, T-032, T-036, T-037, T-041, T-046, T-047, T-048 są poza ścieżką
krytyczną — mogą być pominięte, jeśli czas się kończy, **z wyjątkiem T-036**
(symulacja szumu taggera), która jest warunkiem uczciwości wyniku głównego.

## Zasady dla agenta — czego nie robić

1. Nie „poprawiaj” wyniku przez zmianę hiperparametrów po FREEZE bez wpisu
   w `DEVIATIONS.md`.
2. Nie podmieniaj cicho `*_gold` za `*_pred`, gdy tagger zawiedzie na jakimś
   fragmencie — loguj i raportuj brak.
3. Nie licz p-wartości z dystansów parowych.
4. Nie generuj figury bez kotwicy kontrolnej.
5. Nie uruchamiaj analiz na Koranie przed T-033.
6. Nie zwiększaj liczby przebiegów, żeby „znaleźć coś ciekawego” — liczba
   testów jest częścią wyniku.
7. Gdy zadanie wymaga decyzji merytorycznej (gatunek, chronologia, mapowanie
   tagsetu), przygotuj propozycję i zatrzymaj się na weryfikację człowieka.
