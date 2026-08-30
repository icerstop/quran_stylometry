# 03 — Dane: źródła, przygotowanie, segmentacja

> **Uwaga:** konkretne adresy, licencje, nazwy kolumn i parametry są zamknięte
> w `09_DECISIONS.md`. Ten plik opisuje *co* robimy z danymi; `09_DECISIONS.md`
> mówi *którymi dokładnie* zasobami. Przy rozbieżności wygrywa `09_DECISIONS.md`.

## 1. Źródła i ich rola

| Zasób | Rola w v2 | Uwagi krytyczne |
|---|---|---|
| **EQTB** (Extended Quranic Treebank, repo `NoorBayan/Quranic`) | **Podstawowe** źródło tekstu Koranu | Dostarcza obie ortografie (uthmani + imlāʾī) i pełne pokrycie składniowe w rozszerzonym CoNLL-X (~43 kolumny, ~132,7 tys. tokenów). Warstwa składniowa jest częściowo generowana parserem BiLSTM — traktować jako *silver*, nie gold. |
| **QAC** (corpus.quran.com) | Referencja do ewaluacji taggera + metadane wersetów | 77 430 słów ortograficznych z ręcznie weryfikowaną morfologią; składnia gold tylko dla części korpusu. |
| **OpenITI RELEASE** (Zenodo, najnowszy tag; np. 2023.1.8 lub nowszy) | Korpus kontrolny CTRL | 8 600 dzieł / 3 254 autorów w 2023.1.8. Używać wersji `PRI` z tagiem `CLEANED_VERSION` (bez wstępów, przypisów, indeksów). Teksty pochodzą z Shamela/JK — jakość transkrypcji zmienna. |
| Metadane OpenITI (`*.yml`, KITAB metadata app) | `author_id`, `book_id`, `version_id`, `death_date` | Gatunek w metadanych OpenITI jest **niepewny** — dla wybranych ~80 dzieł etykietuj gatunek ręcznie. |

**Licencje — do sprawdzenia i zapisania w `DATA_LICENSES.md` przed użyciem:**
QAC (GPL-owy model licencyjny), EQTB (licencja repozytorium), OpenITI
(open access, ale poszczególne teksty mają różne pochodzenie). Zadanie T-003.

**Zasada:** wszystkie liczby o korpusach (liczba słów, sur, ajatów) mają być
**wyliczone programowo i zapisane do `results/corpus_stats.json`**, nie
przepisane z dokumentacji. `6236` ajatów to liczba dla rachuby kufijskiej
(Ḥafṣ) — zależy od wydania.

## 2. Dobór korpusu kontrolnego CTRL

Cel: **≥ 60 autorów** (docelowo 100+), ≥ 30 000 tokenów na autora,
≥ 3 dzieła na autora tam, gdzie to możliwe. Rozmiar docelowy 2–4 mln tokenów.

Kryteria selekcji (skrypt + ręczna weryfikacja):
1. `death_date` ≤ 500 AH → warstwa `near-period`; 500–900 AH → `broad`.
2. Dzieło ma ≥ 10 000 tokenów po czyszczeniu.
3. Autor ma ≥ 2 dzieła (twardy warunek dla `V_single` z wielodziełowością).
4. Wykluczyć: dzieła będące kompilacjami cudzych tekstów bez autorskiego głosu
   (słowniki, tabele genealogiczne, indeksy), o ile da się je zidentyfikować.
5. Wykluczyć teksty z anomalnym profilem znaków (proxy błędu OCR, T-011).

## 3. Warstwa kontroli gatunkowej (nowa, obowiązkowa)

Etykieta `genre` z zamkniętej listy:

```
tafsir | hadith_collection | history | fiqh | adab_prose | maqamat_saj |
poetry_diwan | prayer_sermon | theology | biography | other
```

Przypisywana **automatycznie** regułami po tytule — tabela wzorców
w `09_DECISIONS.md §4`. Nie ma etapu ręcznego etykietowania.

Wymagane pokrycie minimalne:
- `maqamat_saj`: ≥ 3 autorów (proza rymowana — najbliższy dostępny analog rejestru),
- `poetry_diwan`: ≥ 5 autorów,
- `prayer_sermon`: ≥ 2 zbiory,
- `hadith_collection`: ≥ 2 (jako kotwica `V_multivoice`).

To jest jedyna realna mitygacja F-04. Nie da się jej pominąć „bo trudno”.

## 4. Normalizacja (G2)

Jeden moduł `normalize_arabic.py`, jedna funkcja, jeden config. Kolejność:

1. Unicode NFC.
2. Usunięcie tatweel `ـ`.
3. Usunięcie znaków pauzy koranicznej, numeracji ajatów, sajda-marks, ozdobników.
4. Usunięcie diakrytyki (harakāt, shadda, sukūn) — w profilu `strip_diacritics`.
5. Ujednolicenie alifów: `أ إ آ ٱ → ا`; `ى → ي` (opcja); `ة → ه` (opcja).
6. Ujednolicenie `ؤ ئ` → forma bazowa (opcja).
7. Usunięcie znaków spoza zakresów arabskich + normalizacja białych znaków.

Profile w configu: `strict` (wszystko powyżej), `light` (bez pkt. 5–6).
Wynik główny liczony na `strict`; `light` jako analiza wrażliwości.

**Wejście dla Koranu: warstwa imlāʾī z EQTB, nie uthmani.** Jeśli EQTB nie
pokrywa jakiegoś tokenu, loguj i raportuj pokrycie — nie podmieniaj cicho.

**Testy jednostkowe obowiązkowe:** idempotencja (`f(f(x)) == f(x)`),
zachowanie liczby tokenów, brak pustych tokenów, snapshot na 50 ręcznie
przygotowanych przypadkach brzegowych.

## 5. Anotacja (G1) — najważniejszy krok pipeline'u

```
                     ┌────────────────────┐
Koran (imlāʾī, norm) ─┤                    ├→ tagi POS/morf (predicted)
                     │  TAGGER PRODUKCYJNY │
CTRL (norm) ─────────┤  (jeden, ten sam)  ├→ tagi POS/morf (predicted)
                     └────────────────────┘

EQTB/QAC gold ──→ TYLKO: (a) ewaluacja taggera, (b) analizy wewnątrz Koranu
```

Tagger produkcyjny jest **wybrany**: CAMeL Tools z bazą `calima-msa-r13`
(GPL-2, pobierana przez `camel_data`). Disambiguator: MLE na laptopie,
BERT unfactored MSA na klastrze. Farasa odpada — patrz `09_DECISIONS.md §1`.

T-014 nie wybiera już narzędzia, tylko **mierzy jego jakość**:
- kryterium: accuracy segmentacji i POS mierzona **na Koranie wobec QAC gold**,
  raportowana jako `token-level accuracy`, `segmentation F1`, `POS accuracy`,
  `lemma accuracy`.
- wynik trafia do preregistration jako liczba, którą raport cytuje przy każdej
  interpretacji cech POS/MORF.

**Symulacja szumu taggera (T-036):** znając accuracy `a` na Quranic Arabic,
wstrzyknij analogiczny szum do gold-tagów Koranu i zmierz, jak przesuwa się
`V_Quran`. Jeśli przesunięcie jest tego samego rzędu co badany efekt — efekt
nie istnieje.

## 6. Segmentacja na okna (G3)

Parametry: `window_size = 400` tokenów ortograficznych (główna),
`{250, 800}` jako wrażliwość. `overlap = 0` dla wszystkiego, co wchodzi do
uczenia i do `V`; `overlap = 0.5` **wyłącznie** dla wykresów lokalnych i CPD,
z flagą `overlapping=true` i zakazem mieszania obu w jednym splicie (G3+).

Reguły:
1. Okno nigdy nie przekracza granicy `surah_id` (Koran) ani `book_id` (CTRL).
2. Reszta krótsza niż `0.6 × window_size` jest doklejana do poprzedniego okna
   tej samej sury/dzieła (max długość `1.6 × window_size`).
3. Sury krótsze niż `0.6 × window_size` (znaczna część 30. dżuz) są łączone
   w **okna kompozytowe** wyłącznie z surami sąsiadującymi *w tym samym bloku
   chronologicznym*, z flagą `composite=true` i listą `surah_ids`.
4. Analiza główna raportowana w dwóch wariantach: z oknami kompozytowymi
   i bez nich. Jeśli wnioski się różnią — to jest wynik do zaraportowania.

Oczekiwana skala: ~77 tys. słów / 400 ≈ **190–200 okien** Koranu. Ta liczba
determinuje `n_w` we wszystkich porównaniach (G6).

## 7. Cytaty koraniczne i near-duplicaty

Dwa różne problemy, nie mieszać:

**(a) Cytaty Koranu w OpenITI** — pipeline z v1 jest dobry, doprecyzowany:
1. normalizacja obu stron tym samym normalizatorem,
2. indeks n-gramów Koranu (`n = 7` słów po normalizacji `strict`),
3. exact match + MinHash/LSH (`num_perm=128`, `threshold=0.8`) dla fuzzy,
4. usunięcie dopasowań z marginesem ±3 tokeny,
5. **raport skuteczności**: odsetek usuniętego tekstu per dzieło, ręczna
   inspekcja 100 losowych dopasowań i 100 losowych niedopasowań (precision/recall
   szacowany ręcznie — bez tego nie wiesz, czy usunąłeś 20% tafsīru czy 2%).

Artefakty: `OPENITI_RAW`, `OPENITI_CLEAN`, `quote_removal_report.json`.
Wszystkie eksperymenty na `OPENITI_CLEAN`.

**(b) Redundancja wewnętrzna** (F-11) — mierzona osobno dla każdego korpusu:
`internal_duplication_rate` = odsetek 7-gramów występujących ≥ 2 razy w obrębie
korpusu. Wariant analizy `dedup=true` usuwa powtórzone wystąpienia. Raport
zawiera obie wersje.

## 8. Chronologia jako zmienna (F-08, F-09)

**Plik jest dostarczony gotowy:** `data_reference/chronologies.csv`, 114 wierszy,
wygenerowany i zweryfikowany (86 mekkańskich, 28 medyńskich, 35 sur z wersetowymi
wyjątkami). Skopiuj do `data/reference/` i nie modyfikuj ręcznie.

Kolumny: `surah_id, order_canonical, order_traditional, order_noldeke,
period_traditional, composite_flag, exception_verses, exception_period,
place_note, source`.

Trzy rzeczy do zapamiętania przy interpretacji:
- `order_traditional` i `order_noldeke` różnią się pozycją tylko dla 13 sur
  (Spearman ρ ≈ 0,99). To **nie jest** mocna analiza wrażliwości i tak ma być
  opisane w raporcie.
- Prawdziwy kontrast chronologiczny to `order_canonical` vs `order_traditional`.
- Najmocniejsza kontrola to `exception_verses`: okna zawierające wersety
  przypisane do przeciwnego okresu dostają etykietę `mixed` i w wariancie
  głównym są wykluczane. Zastępuje to nieosiągalną trzecią chronologię.

Figura obowiązkowa: macierz zgodności (Spearman ρ) między uporządkowaniami,
z jawnie podaną wartością ρ — żeby czytelnik widział, jak bardzo są podobne.

## 9. Schemat rekordu (rozszerzony wobec v1)

```json
{
  "document_id": "quran_s002_w003",
  "corpus": "quran|ctrl|pseudo|mixture|anchor",
  "author_id": null,
  "book_id": null,
  "version_id": null,
  "genre": "quran",
  "death_date_ah": null,
  "period_bucket": "near|broad|na",

  "surah_id": 2,
  "surah_ids": [2],
  "verse_start": 141,
  "verse_end": 176,
  "composite": false,
  "overlapping": false,

  "period_traditional": "medinan",
  "order_cairo": 87,
  "order_noldeke": 91,
  "order_sadeghi": 88,
  "composite_flag": 0,

  "text_norm_strict": "...",
  "text_norm_light": "...",
  "tokens": [],
  "segments": [],
  "lemmas_pred": [],
  "pos_pred": [],
  "morph_pred": [],
  "lemmas_gold": [],
  "pos_gold": [],
  "morph_gold": [],
  "deprel_gold": [],

  "n_tokens": 400,
  "n_segments": 663,
  "n_verses": 36,
  "mean_verse_len": 11.1,

  "annotation_source": "predicted",
  "normalizer_version": "strict-1.0.0",
  "tagger_version": "camel-msa-1.5.2",
  "split": "ctrl_train|ctrl_calib|ctrl_test|target"
}
```

Kluczowe: pola `*_pred` i `*_gold` są **rozdzielone na poziomie schematu**, żeby
naruszenie G1 było niemożliwe przez przypadek. Test `test_no_gold_in_crosscorpus.py`
sprawdza, że żadna macierz cech użyta w porównaniu Koran↔CTRL nie została
zbudowana z pól `*_gold`.

## 10. Splity

```
CTRL-TRAIN   ~60% autorów   → fitowanie słowników, trening AA/AV
CTRL-CALIB   ~15% autorów   → kalibracja progów AV
CTRL-TEST    ~25% autorów   → ewaluacja generalizacji (autorzy niewidziani)
TARGET       Koran + kotwice RQ6 → tylko transformacja, nigdy fitowanie
```

Split po `author_id` (nie po `book_id`, nie po oknach). Wewnątrz AA
dodatkowo `GroupKFold(groups=book_id)`. Seed w configu.

## 11. Korpusy syntetyczne

**PSEUDO-BOOK** (jeden na autora, tylko autorzy z ≥ 2 dziełami):
próbkuj okna z różnych dzieł tego autora, proporcjonalnie do liczby dzieł,
do osiągnięcia `n_w` = tyle, ile ma Koran. Powtórz `B = 200` razy.

**MIXTURE-k** (k ∈ {2, 3, 5}): losuj k autorów, próbkuj okna równomiernie,
`n_w` jak wyżej, `B = 200` losowań na k. Dodatkowy wariant `mixture-k-samegenre`
(k autorów z tego samego gatunku) — bo mieszanka gatunków sztucznie zawyża `V`.

**ANCHOR** (RQ6): dywan pojedynczego poety, kolekcja hadisów, Nahj al-Balāgha —
traktowane dokładnie jak Koran w całym pipeline.
