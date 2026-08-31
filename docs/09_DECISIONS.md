# 09 — Decyzje zamknięte

Ten plik jest wiążący. Każdy wybór, który wcześniej wymagał człowieka, jest tu
rozstrzygnięty razem z uzasadnieniem i regułą fallbacku. Wszystko darmowe,
bez rejestracji, bez LDC, bez paywalla.

---

## 1. Narzędzia — zamknięte

| Rola | Wybór | Dlaczego, i co odpada |
|---|---|---|
| Segmentacja + morfologia + POS (produkcyjny tagger, G1) | **CAMeL Tools**, baza `calima-msa-r13`, disambiguator MLE (laptop) lub BERT unfactored MSA (klaster) | `calima-msa-r13` jest na GPL-2, pobierana przez `camel_data`, oparta na publicznie dostępnej `almor-msa-r13` z MADAMIRA. Nie wymaga licencji LDC. |
| ~~Farasa~~ | **odpada całkowicie** | Wymaga JVM, licencja ogranicza użycie komercyjne, i nie wnosi nic ponad CAMeL po tym, jak segmentacja morfologiczna jest już rozwiązana. Usuwa jedną zależność systemową. |
| Parser zależnościowy | **żaden** | Składnia Koranu pochodzi gotowa z EQTB; składnia cross-corpus została wycięta z designu (F-15). Nie instalujemy parsera. |
| Model językowy (E-14) | **CAMeLBERT-CA** (`CAMeL-Lab/bert-base-arabic-camelbert-ca`), HuggingFace, jeden pooling: mean z 4 ostatnich warstw | Eksploracyjne, jeden model, jak w `05_EXPERIMENTS.md`. |
| Change-point detection | `ruptures` — **PELT + KernelCPD** | Dwa algorytmy, nie cztery. |
| Near-duplicate / cytaty | `datasketch` (MinHash + LSH) + własny indeks n-gramów | Czysty Python, bez zależności systemowych. |

**Konsekwencja:** cały stack to `pip install`. Zero JVM, zero Dockera dla
zależności zewnętrznych, zero rejestracji.

---

## 2. Źródła danych — zamknięte, z weryfikowalnym adresem

### 2.1. Tekst Koranu — EQTB
- Repo: `https://github.com/NoorBayan/Quranic`, katalog `corpus/`.
- **Licencja: MIT.**
- Format: rozszerzony CoNLL-X, jeden token na wiersz.
- Kolumny, na które liczy pipeline (nazwy z README repo):
  `tid, sentence_id, verse_id, word_id, tok_id, location, chapter_id,`
  `uthmani_token, imlaai_token, uthmani_unicode, imlaai_unicode, phonetic, trans,`
  `pos, pos_ar, features, segment, lemma, lemma_ar, root, root_ar,`
  `verb_form, prefix, suffix, verb_aspect, nominal_state, verb_mood, nominal_case,`
  `derived_nouns, verb_voice, person, gender, number,`
  `special_group, rel_label, rel_label_ar, ref_token_id,`
  `is_constituent, constituent_node, constituent_position, constituents, constituent_label`
- **Wejście do pipeline'u: kolumna `imlaai_token`** (G2). Ortografia uthmani
  służy wyłącznie do kontroli wrażliwości.
- README jest niekonsekwentne przy `uthmani_unicode` / `imlaai_unicode`
  (raz opisane jako Buckwalter, raz jako Unicode) — **sprawdź empirycznie na
  pierwszych 100 wierszach i zapisz ustalenie w `results/eqtb_schema.json`.**
- Warstwa składniowa jest częściowo generowana parserem BiLSTM → traktuj jako
  **silver**, oznacz w metadanych, nie nazywaj gold.

**Rozstrzygnięte empirycznie (T-009, session 2):** tabela na poziomie tokenu
NIE leży jako płaski plik w `corpus/` — jest spakowana w `corpus/Quranic.rar`
→ `Quranic.csv` (UTF-16-LE, TAB). Płaski `corpus/Quran.csv` to osobny,
5-kolumnowy plik na poziomie ajatu, nieużywany do budowy `Window`.
`T-009` musi: pobrać `.rar`, rozpakować (zależność `7-Zip` w `pyproject.toml`,
sekcja `[nlp]` lub dedykowana), sparsować `Quranic.csv`.

Mapowanie nazw kolumn (40/42 zgodne werbatim; dwa wyjątki):
- `constituent_position` → w źródle nazywa się **`constituents_loc`**
  (format `[start-end]`, zgodny z opisem README). Mapuj 1:1 przy parsowaniu.
- `constituent_node` → **nierozstrzygnięte, i to jest w porządku.** Kandydat
  `head_rel` (jedyne pole binarne w próbce) ma tylko poszlakowe dowody, a samo
  README źródła sygnalizuje niejednoznaczność tej kolumny. Ponieważ żadna
  rodzina cech w `docs/04_FEATURES.md §F7` nie korzysta z pól `constituent_*`
  (składnia w tym projekcie opiera się wyłącznie na relacjach zależnościowych:
  `rel_label`, `ref_token_id`), **to pole zostaje nullable/`unmapped`** w
  schemacie `Window`. Nie blokuj T-009 na jego rozstrzygnięciu. Jeśli
  przyszły eksperyment kiedykolwiek będzie go potrzebował — rozstrzygnąć
  wtedy, z konkretnym kontekstem użycia, nie na sucho.

**Zasada dla `verify-sources`:** sprawdza tylko osiągalność `.rar` (rozmiar,
opcjonalnie hash), nigdy nie rozpakowuje przy rutynowym uruchomieniu. Pełna
ekstrakcja i parsowanie kolumn to praca `T-009`, wykonana raz, z wynikiem
cache'owanym — nie powtarzana przy każdym `make verify-sources`.

### 2.2. Referencja morfologiczna — QAC
- `https://corpus.quran.com/` — plik morfologii (`quranic-corpus-morphology-*.txt`).
- Rola: **wyłącznie ewaluacja taggera** (T-014). Nigdy jako cechy cross-corpus.
- Jeśli pobranie zawiedzie: ewaluacja taggera odbywa się wobec kolumn
  morfologicznych EQTB, z adnotacją w raporcie, że referencja jest EQTB, nie QAC.
  **To jest dozwolony fallback, nie blocker.**

### 2.3. Korpus kontrolny — OpenITI
- Metadane: release na Zenodo (DOI `10.5281/zenodo.3082463` prowadzi do
  najnowszej wersji) — **najpierw pobierz sam plik metadanych TSV**, nie korpus.
- Teksty: pobieraj **selektywnie** przez `raw.githubusercontent.com` dla
  wybranych `versionURI`, z repozytoriów 25-letnich (`OpenITI/0525AH` itd.).
  Nie klonuj całego release (2,27 mld słów).
- Filtr: `status == "pri"` **i** tag `CLEANED_VERSION` (bez wstępów, przypisów,
  indeksów wydawcy).
- Oczekiwany rozmiar po selekcji: **1,5–2 GB na dysku**, nie 25 GB.

### 2.4. Chronologia — **plik dostarczony, nic nie wpisujesz ręcznie**
- `data/reference/chronologies.csv` (dostarczony w tym repo), 114 wierszy, wygenerowany
  z tabeli Tanzil (`tanzil.net/docs/revelation_order`, oparta na al-Zanjānīm /
  Ibn ʿAbbāsie), zweryfikowany: 86 mekkańskich, 28 medyńskich, 35 sur
  z wersetowymi wyjątkami.
- Kolumny: `surah_id, order_canonical, order_traditional, order_noldeke,`
  `period_traditional, composite_flag, exception_verses, exception_period,`
  `place_note, source`.
- `order_noldeke` wyliczony deterministycznie z porządku tradycyjnego przez dwie
  udokumentowane zmiany (sura 110 przenoszona między 59 a 24; sura 62 przed 64 i 61).
- **Uczciwe ograniczenie, które ma trafić do raportu:** te dwa uporządkowania
  różnią się pozycją tylko dla 13 sur, więc Spearman ρ ≈ 0,99. Analiza
  wrażliwości „trzy niezależne chronologie" z planu v1 **nie jest wykonalna
  na darmowych źródłach** — Sadeghi (Arabica 58) i Blachère są za paywallem.
  Zamiast tego prawdziwa wrażliwość opiera się na:
  1. `order_canonical` vs `order_traditional` (te różnią się drastycznie),
  2. wykluczaniu 35 sur kompozytowych,
  3. **relabelingu wersetowym** z `exception_verses` — okna zawierające wersety
     przypisane do przeciwnego okresu dostają etykietę `mixed` i są w wariancie
     głównym wykluczane. To jest mocniejsza kontrola niż trzecia chronologia.
- `order_sadeghi` **usunięte z designu.** F9 (baseline literaturowy) pozostaje,
  ale definiowany operacyjnie: częstości najczęstszych morfemów + średnia długość
  ajatu. To rekonstrukcja rodziny markerów, nie odtworzenie konkretnej pracy —
  i tak ma być opisane w raporcie.

---

## 3. Selekcja autorów — algorytm deterministyczny, bez decyzji człowieka

Wejście: metadane OpenITI. Wyjście: `data/interim/ctrl_manifest.csv`.

```
1. filtr: status == "pri" AND "CLEANED_VERSION" in tags AND language == "ara"
2. filtr: 0 < death_date_ah <= 900
3. przypisz genre wg reguł z §4 (tagi OpenITI jako sygnał główny, tytuł jako
   fallback) — MUSI poprzedzać filtr jakości, bo krok 4 jest gatunkowo-zależny
4. filtr jakości: udział znaków spoza [arabski + spacja + interpunkcja] < 5%
                  AND średnia długość "słowa" w zakresie:
                     - 2.5–8.0 znaków dla genre ∈ {poetry_diwan, maqamat_saj}
                     - 3.0–8.0 znaków dla wszystkich pozostałych gatunków
   (dolny próg 3.0 myli krótkie tokeny wiersza z artefaktem OCR — rozstrzygnięte
   empirycznie w sesji T-011, dowód: poezja mean_word_length ≈ 2.87 na próbce
   czystych, znanych tekstów jak Mutanabbī)
5. agregacja po author_id: keep jeśli
      (n_books >= 2 AND total_tokens >= 30000 AND max(book_tokens) >= 10000)
      OR
      (genre ∈ {maqamat_saj, poetry_diwan, prayer_sermon, hadith_collection}
       AND n_books == 1 AND book_tokens >= 15000)   # wyjątek, patrz niżej
6. wyklucz book_id, którego tytuł pasuje do EXCLUDE_TITLE_PATTERNS (§4)
7. sortuj autorów malejąco po total_tokens, w obrębie każdego gatunku
8. weź do 12 autorów na gatunek (limit anty-dominacyjny), aż zbierzesz >= 60
9. jeśli po kroku 8 masz < 60 autorów: poluzuj krok 5 do total_tokens >= 20000
   i powtórz. Jeśli nadal < 60 → BLOCKER, zatrzymaj się i zapytaj.
```

**Usunięty check (sesja T-011):** `udział linii dłuższych niż 2000 znaków < 2%`
wypadł z filtra jakości. Zmierzone: 0/63 plików w próbce miało cokolwiek powyżej
progu — OpenITI łamie linie w sposób, który strukturalnie nigdy go nie
przekracza. Check nie niósł żadnej informacji; dwa pozostałe (znaki spoza
arabskiego, długość słowa) już poprawnie odróżniają OCR od czystego tekstu
(7/10 vs 0/3 na próbce kontrolnej z T-011).

**Wyjątek jednodziełowy dla czterech gatunków-kotwic (sesja T-011, krok 5.)**
Standardowy próg `n_books ≥ 2` zderzył się z rzeczywistością gatunku
`maqamat_saj`: twórca gatunku (al-Hamadhānī) i inni znani przedstawiciele są
znani z jednego wielkiego dzieła, nie z kariery wielotomowej. Zamiast obniżać
docelowe minimum pokrycia (§4, ryzyko dopasowania celu do wyniku po fakcie),
dopuszczam substantywny wyjątek: **autor z jedną książką ≥15 000 tokenów
(1,5× istniejący próg `max(book_tokens) ≥ 10000`) wchodzi do CTRL**, jeśli
jego gatunek ma twarde minimum pokrycia. Zasada jest ogólna — stosowana
identycznie do wszystkich czterech kategorii, nie tylko tam, gdzie akurat
brakuje autorów.

**Ograniczenie, obowiązkowe do wyegzekwowania w kodzie:** autorzy przyjęci
tą ścieżką **nie kwalifikują się do PSEUDO-BOOK** (`docs/03_DATA.md §11`
i tak niezależnie wymaga `n_books ≥ 2`) — kontrybuują tylko do ogólnej puli
CTRL i analiz gatunkowych (E-05b). `ctrl_manifest.csv` musi nieść kolumnę
`admission_path: "standard" | "single_work_exception"`, żeby to było zawsze
widoczne w dalszych analizach, nie ukryte w agregacie.

**ROZSTRZYGNIĘTE — limit tokenów per autor (sesja T-013→T-014).**
Zmierzone: CTRL po normalizacji ma 206,8 mln tokenów dla 106 autorów —
o rząd wielkości więcej niż zakładał szacunek rozmiaru dysku w §2.3
(1,5–2 GB miało być sanity checkiem przeciw pobraniu całego release'u, nie
celem tokenowym). Przyczyna strukturalna: krok 7 algorytmu w §3 sortuje
autorów malejąco po `total_tokens`, więc celowo preferuje najbardziej
płodnych — mediana per autor to 1,52 mln tokenów, więc to nie jest problem
kilku odstających gigantów, tylko cecha całej selekcji.

**Limit: 200 000 tokenów na autora.** Uzasadnienie metodologiczne, nie
budżetowe (żadna wartość z symulowanej siatki {50k…300k} i tak nie schodzi
do pierwotnego, jak się okazało błędnego, szacunku GPU z §10_COMPUTE.md —
poprawka budżetu jest osobną decyzją poniżej, nie powodem tego limitu):
~6,7× próg wejścia do korpusu (30 000, `§3` krok 5) i ~2,6× rozmiar Koranu
(~77 429 tokenów — wielkość pojedynczego losowania PSEUDO-BOOK), co daje
zapas na sensowne resamplowanie bootstrapowe (`bootstrap_B: 200`) bez
pozwalania jednemu autorowi zdominować trening AA/AV. Efekt: 19,68 mln
tokenów łącznie, 89/106 autorów przyciętych.

**Sposób realizacji limitu (obowiązkowy, nie do pominięcia):** proporcjonalna
alokacja limitu między dziełami danego autora, z losowym ciągłym fragmentem
w obrębie każdego dzieła — **nigdy obcinanie po kolejności dokumentów**.
Truncation od początku największego dzieła zniszczyłby różnorodność
międzydzieł, dla której PSEUDO-BOOK (`docs/03_DATA.md §11`) w ogóle istnieje.
Realizowane jako nowy krok między T-013 (gotowe) a T-015 (tagowanie) —
operuje na już znormalizowanym tekście, nie wymaga ponownego uruchamiania
T-013. Artefakt: `data/interim/ctrl_capped/` + manifest z kolumnami
`author_id, book_id, tokens_before_cap, tokens_after_cap, span_seed`.

**Poprawka budżetu obliczeniowego:** patrz `docs/10_COMPUTE.md` — szacunek
„2–4 mln tokenów, 3–8 h" był zgadywany przed poznaniem realnej skali CTRL
i jest nieaktualny. Nowy budżet ustalany empirycznie przez pilotaż
przepustowości w ramach `dryrun.sbatch` dla H1, nie przez kolejne zgadywanie.

Podział na warstwy: `near-period` = `death_date_ah <= 500`,
`broad` = `501–900`. Obie warstwy analizowane osobno w E-05.

---

## 4. Gatunek — klasyfikacja dwustopniowa: tagi OpenITI, potem tytuł

**Rozstrzygnięte empirycznie (sesja T-011):** czysta klasyfikacja po tytule
pokrywa tylko ~26% metadanych (74,2% ląduje w `other`, identycznie na pełnej
tabeli 14 107 wierszy i na puli kandydatów n=5075 — więc to nie jest efekt
selekcji, tytuły po prostu w większości nie pasują do prostych wzorców).

**Krok 1 — sygnał główny: tagi OpenITI.** Metadane niosą ustrukturyzowane
tagi (`_HADITH`, `_FIQH`, `_TARAJIM`, `GAL@literature-*` i pokrewne — oparte
na klasyfikacji bibliograficznej Brockelmanna). Zanim zbudujesz mapowanie:
**empirycznie wylistuj wszystkie unikalne wartości/wzorce tagów obecne w TSV**
(ten sam standard dowodowy co przy `constituent_node` w T-009 — żadnego tagu
nie mapuj na gatunek bez pokazania próbki tytułów, które za nim stoją).
Zapisz mapowanie tag → genre w `data/reference/openiti_tag_genre_map.csv`
z kolumną `evidence_sample` (3–5 tytułów na tag). To zastępuje tytuł jako
główne źródło sygnału tam, gdzie tag jest obecny.

**Krok 2 — sygnał zapasowy: wzorce tytułowe.** Tabela poniżej stosowana tylko
tam, gdzie krok 1 nie dał wyniku.

**Krok 3 — residual.** Co nie trafi w kroku 1 ani 2, zostaje `other`.
To jest zaakceptowany stan końcowy (nie forsuj klasyfikacji na siłę) —
wymagane jest wyłącznie twarde pokrycie minimalne z reguły pokrycia poniżej,
nie zniknięcie kategorii `other`. Miękki cel (nie blokujący): udział `other`
w finalnie wybranych 60+ autorach poniżej 50% — pomaga to E-05b
(dekompozycja wariancji po gatunku), ale nie jest warunkiem T-011.

Dopasowanie w kroku 2 po znormalizowanym tytule (bez diakrytyki, lowercase,
translit lub arabski). Pierwsze trafienie wygrywa; kolejność reguł jest
częścią decyzji.

| Kolejność | Wzorce w tytule | `genre` |
|---|---|---|
| 1 | `maqam*` / `مقامات` | `maqamat_saj` |
| 2 | `diwan` / `ديوان` / `shi'r` / `شعر` | `poetry_diwan` |
| 3 | `sahih` / `sunan` / `musnad` / `muwatta` / `صحيح` / `سنن` / `مسند` | `hadith_collection` |
| 4 | `tafsir` / `تفسير` / `jami' al-bayan` / `ahkam al-qur'an` | `tafsir` |
| 5 | `du'a` / `دعاء` / `sahifa` / `khutab` / `خطب` / `munajat` | `prayer_sermon` |
| 6 | `tarikh` / `تاريخ` / `akhbar` / `أخبار` / `futuh` | `history` |
| 7 | `tabaqat` / `طبقات` / `sira` / `سيرة` / `wafayat` / `mu'jam al-udaba` | `biography` |
| 8 | `fiqh` / `فقه` / `mabsut` / `umm` / `hidaya` / `ahkam` | `fiqh` |
| 9 | `kalam` / `كلام` / `'aqida` / `عقيدة` / `milal` / `usul al-din` | `theology` |
| 10 | `adab` / `أدب` / `bayan` / `amali` / `nawadir` / `rasa'il` | `adab_prose` |
| 11 | brak trafienia | `other` |

**Reguła pokrycia:** jeśli po selekcji brakuje minimalnego pokrycia
(`maqamat_saj` ≥ 3 autorów, `poetry_diwan` ≥ 5, `prayer_sermon` ≥ 2,
`hadith_collection` ≥ 2), dociągnij brakujących autorów z pełnych metadanych
OpenITI **ignorując krok 8** (limit anty-dominacyjny), sortując po `total_tokens`.
Kontrola gatunkowa ma priorytet nad równomiernością.

`EXCLUDE_TITLE_PATTERNS` (dzieła bez autorskiego głosu, wykluczane w kroku 5):
`mu'jam` w znaczeniu słownika (`lisan al-'arab`, `qamus`, `sihah`, `taj al-'arus`),
`fahras*`, `kashf al-zunun`, `ansab` (tablice genealogiczne), `mu'jam al-buldan`.

---

## 5. Kotwice zewnętrzne (RQ6) — konkretne dzieła

Pobierane z OpenITI po `versionURI`. Jeśli konkretne dzieło jest niedostępne,
zastąp je innym z tego samego gatunku i epoki, i **zaloguj podmianę**.

| Rola w skali | Dzieło | Oczekiwanie |
|---|---|---|
| jednoautorskie, rymowane (saʿ) | Maqāmāt al-Ḥarīrī | nisko |
| jednoautorskie, rymowane (saʿ) | Maqāmāt al-Hamadhānī | nisko |
| jednoautorskie, poezja | Dīwān al-Mutanabbī | nisko |
| jednoautorskie, poezja | Dīwān Abī Nuwās | nisko |
| jednoautorskie, liturgiczne | al-Ṣaḥīfa al-Sajjādiyya | nisko |
| **wielogłosowe** | Ṣaḥīḥ al-Buchārī (matny wielu nadawców) | wysoko |
| **wielogłosowe** | Sunan Abī Dāwūd | wysoko |
| tekst kompilowany, status dyskutowany | Nahj al-Balāgha | kalibracja skali |

Pierwsze pięć to materiał do E-07 (bramka OOD dla AV). Dwa kolejne dają kotwicę
`V_multivoice`. Nahj al-Balāgha jest drugim przypadkiem testowym, żeby wynik dla
Koranu nie stał samotnie na skali.

---

## 6. Parametry liczbowe — zamrożone

```yaml
seed: 20260830
token_unit: orthographic_word
window_size: 400            # wrażliwość: 250, 800
overlap_main: 0.0
overlap_local: 0.5          # tylko wykresy lokalne i CPD
min_tail_ratio: 0.6
max_window_ratio: 1.6
min_authors: 60
min_tokens_per_author: 30000
min_works_per_author: 2
bootstrap_B: 200
permutations: 10000
mfw_grid: [100, 300, 1000, 3000]
char_ngram_range: [3, 5]
char_max_features: 50000
quote_ngram_n: 7
minhash_num_perm: 128
minhash_threshold: 0.8
gate_domain_probe_auc_max: 0.98
gate_av_ood_eer_max: 0.35
av_pairs_max_per_split: 400000
av_hard_negative_ratio: 0.7   # udział par DIFFERENT dobranych same-genre/same-era
```

`window_size: 400` daje ~190–200 okien Koranu; ta liczba ustala `n_w` dla
wszystkich porównań `V` (G6) i jest wyliczana, nie wpisywana.

---

## 7. Licencje — do wpisania w `DATA_LICENSES.md` bez dalszej analizy

| Zasób | Licencja | Konsekwencja |
|---|---|---|
| EQTB (`NoorBayan/Quranic`) | MIT | pełna swoboda, wymaga atrybucji |
| QAC morfologia | GPL-owy model licencyjny corpus.quran.com | używane tylko do ewaluacji, nie redystrybuujemy |
| OpenITI | **CC-BY-NC-SA-4.0** (zweryfikowane empirycznie, release 2025.1.9, DOI 10.5281/zenodo.17767721) | kompatybilne z niekomercyjnym użyciem badawczym tego projektu **pod dwoma warunkami, oba już wymuszone przez design repo**: (1) nie redystrybuujemy tekstów źródłowych — `.gitignore` wyklucza `data/` poza `data/reference/`, do repo trafiają tylko manifesty, hashe i cechy pochodne; (2) publikacja wyników (raport, dashboard, praca) pozostaje niekomercyjna. Jeśli w przyszłości pojawi się zamiar komercyjnego wykorzystania — ta decyzja wymaga ponownego rozpatrzenia, nie jest generalnym zezwoleniem. |
| CAMeL Tools kod | MIT | — |
| `calima-msa-r13` | GPL-2 | jeśli kiedykolwiek redystrybuujesz pipeline z bazą, całość na GPL-2 |
| CAMeLBERT-CA | licencja modelu na HF | tylko wnioskowanie, nie fine-tuning |
| `chronologies.csv` | dane z tanzil.net, atrybucja w pliku | — |

**Zasada dla repo:** commitujemy kod, configi, manifesty, hashe i wyniki.
Nie commitujemy tekstów źródłowych. `data/` w `.gitignore` poza `data/reference/`.

---

## 8. Co zostało wycięte i już nie wraca

- Farasa i porównanie trzech segmenterów → jeden tagger, ewaluowany wobec QAC.
- `order_sadeghi` i trzecia chronologia → niedostępne za darmo, zastąpione
  relabelingiem wersetowym.
- Cztery transformery × trzy poolingi → jeden model, jeden pooling.
- Cztery algorytmy CPD → dwa.
- Cechy syntaktyczne w porównaniach cross-corpus → tylko wewnątrz Koranu.
- Ręczne etykietowanie gatunku → reguły z §4.
- Ręczna selekcja autorów → algorytm z §3.
