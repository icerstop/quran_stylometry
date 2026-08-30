# 04 — Rodziny cech i polityka fitowania

## 0. Reguły wspólne (obowiązkowe)

1. **G4 — fitowanie tylko na CTRL-TRAIN.** Słownik, `min_df`, IDF, `μ`, `σ`,
   selekcja MFW — wyłącznie z CTRL-TRAIN. Koran, CTRL-TEST, kotwice i korpusy
   syntetyczne są tylko `transform()`. Vectorizer zapisany do
   `models/vectorizers/<family>_<config_hash>.joblib`.
2. **Każda rodzina ma własny plik macierzy** w `data/features/<family>/`
   (format `.npz` sparse + `.parquet` z indeksem `document_id`). Nigdy nie
   przeliczaj cech w notebooku.
3. **Każda rodzina deklaruje swoją domyślną metrykę dystansu** (tabela w §10).
4. **Każda rodzina deklaruje status**: `core` (liczy się do wniosku głównego),
   `support`, `circular` (nie może uzasadniać wniosku chronologicznego),
   `exploratory`.
5. Nie łączymy rodzin do jednego wektora, dopóki każda nie ma osobnego wyniku.
   Konfiguracja `ALL` powstaje jako ostatnia i jest `support`.

## F1 — Character n-grams  · status: `core`

```python
TfidfVectorizer(
    analyzer="char_wb",       # char_wb, nie char: nie sklejamy przez granice slow
    ngram_range=(3, 5),
    min_df=5,
    max_features=50_000,
    sublinear_tf=True,
    lowercase=False,
)
```

**Na co uważać:** to rodzina najbardziej wrażliwa na ortografię (F-03). Liczona
na `text_norm_strict` po warstwie imlāʾī. Obowiązkowy wariant kontrolny bez
diakrytyki i bez ligatur. Jeśli domain probe (E-01) na tej rodzinie daje
AUC > 0.98, rodzina traci status `core` i jest raportowana z ostrzeżeniem.

## F2 — Function words / częste morfemy  · status: `core`

Lista **nie jest ręcznie pisana**. Budowa:
1. Weź tagi POS z taggera produkcyjnego na CTRL-TRAIN.
2. Wybierz segmenty o POS ∈ {PREP, CONJ, PART, PRON, DEM, REL, NEG, INTG, SUB}.
3. Weź `K` najczęstszych form (siatka `K ∈ {100, 300, 1000}`).
4. Cechy: częstość względna `f_w = count(w) / n_segments_okna`.

**Krytyczne:** proklityki (`wa-`, `fa-`, `bi-`, `li-`, `ka-`, `al-`, `sa-`) muszą
być liczone jako osobne jednostki — czyli **F2 wymaga segmentacji
morfologicznej** (F-16). Wersja bez segmentacji jest bezużyteczna dla arabskiego
i nie wolno jej po cichu podstawić.

Dodatkowo: wariant „common morphemes” w duchu Sadeghiego (2011) — patrz F9.

## F3 — Lexical (words / lemmas / roots)  · status: `support`, wysokie ryzyko topic leakage

TF-IDF dla: `word 1-2 gram`, `lemma 1-2 gram`, `root 1-2 gram`.
Rdzenie w arabskim są **bardziej**, nie mniej, nośnikiem semantyki — nie
traktuj ich jako reprezentacji „odsemantyzowanej”. Ta rodzina istnieje po to,
żeby zmierzyć górną granicę wpływu tematu, nie żeby uzasadniać wnioski.

## F4 — POS n-grams  · status: `core`

`POS 1-3 gram`, częstości względne + TF-IDF (dwa warianty).
Tagi z **taggera produkcyjnego po obu stronach** (G1).
Raport zawsze obok: accuracy taggera na Quranic Arabic z T-014.

## F5 — Morfologia  · status: `core`

Rozkłady kategorii: person, gender, number, case, mood, voice, aspect,
definiteness, proclitics, enclitics + n-gramy pełnych tagów (1-2 gram).
Cechy jako częstości względne, następnie CLR/logit-transform (to są dane
kompozycyjne — surowe proporcje w metryce euklidesowej są problematyczne).

## F6 — Structural  · status: `core`

- długość słowa: średnia, mediana, wariancja, skośność;
- długość ajatu/zdania: średnia, mediana, wariancja (dla CTRL: jednostka
  zdefiniowana przez interpunkcję/mARkdown — **musi być udokumentowana**, bo
  nie jest porównywalna z ajatem wprost);
- znaki na token;
- bogactwo leksykalne: MTLD, HD-D, Maas, Yule's K (**nie** surowe TTR);
- entropia leksykalna, `repetition_rate`.

**Uwaga:** wszystkie miary bogactwa leksykalnego są wrażliwe na długość —
dlatego G6 (matching długości) jest tu warunkiem sine qua non.

## F7 — Składnia  · status: `support`, **tylko wewnątrz Koranu**

Częstości relacji zależnościowych, średni dependency distance, głębokość
drzewa, branching factor, bigramy relacji, `head POS → dependent POS`.
Źródło: warstwa EQTB (silver). **Wyłączona z AA, AV i z porównania `V`**
Koran↔CTRL, ponieważ nie istnieje porównywalna anotacja po stronie OpenITI (F-15).
Używana w: E-09 (Meccan/Medinan), E-11 (change points), E-12.

## F8 — Prozodia i formuły  · status: `circular` (nowa rodzina)

Tego nie było w v1, a to jest miejsce, gdzie realnie żyje sygnał
Meccan/Medinan — i jednocześnie miejsce, z którego wyprowadzono chronologię.

- rozkład długości ajatu (średnia, wariancja, kwantyle);
- litera/klaster rymu na końcu ajatu (`fāṣila`), entropia rymu w oknie,
  długość serii tego samego rymu;
- obecność i częstość formuł otwierających: `qul`, `yā ayyuhā alladhīna āmanū`,
  `yā ayyuhā al-nās`, formuły przysięgi (`wa-`+rzeczownik kosmiczny), `inna`;
- `sura opening type` (litery mukattaʿa, przysięga, chwała, wezwanie itd.);
- odsetek ajatów kończących się typowymi klauzulami rymowanymi.

**Reguła:** F8 nie może być jedynym uzasadnieniem wniosku o chronologii —
byłoby to wnioskowanie z tych samych cech, z których chronologię zbudowano.
F8 służy do: (a) zmierzenia, ile sygnału chronologicznego jest „darmowe”,
(b) wyregresowania go przy testach G7.

## F9 — Baseline literaturowy (Sadeghi-style)  · status: `core-baseline`

Odtworzenie rodziny markerów używanych w Arabica 58 (2011): częstości
wybranych częstych morfemów + długość ajatu, jako **jawny punkt odniesienia**.
Cel: pokazać, czy nowoczesne reprezentacje w ogóle wnoszą coś ponad markery
sprzed 15 lat. Jeśli nie wnoszą — to też jest wynik.

Dodatkowo: implementacja i **krytyczny test** „criterion of concurrent
smoothness” — sprawdzić, czy kryterium daje ten sam wynik na korpusach
MIXTURE (gdzie wiemy, że autorów jest wielu). To bezpośrednia odpowiedź na
opublikowaną krytykę tego kryterium.

## 10. Konfiguracje do ablacji i metryki

| Konfiguracja | Rodziny | Status |
|---|---|---|
| `CHARACTER` | F1 | core |
| `FUNCTIONAL` | F2 + F4 + F5 + F6 | core |
| `LEXICAL` | F3 | support (górna granica topic leakage) |
| `PROSODIC` | F8 | circular |
| `BASELINE_LIT` | F9 | core-baseline |
| `SYNTAX_Q` | F7 | support, tylko Koran |
| `ALL` | F1–F6 | support |

Domyślne metryki dystansu:

| Rodzina | Metryka główna | Alternatywa |
|---|---|---|
| F1 char n-gram | Cosine Delta | cosine |
| F2 function words | Burrows's Delta (z-score) | Eder's Delta |
| F3 lexical | cosine | Cosine Delta |
| F4 POS | Jensen–Shannon | cosine |
| F5 morfologia | Aitchison (po CLR) | JS |
| F6 structural | Mahalanobis (kowariancja z CTRL-TRAIN) | euclidean po standaryzacji |
| F8 prozodia | euclidean po standaryzacji | — |

Siatka MFW dla Delty: `{100, 300, 1000, 3000}` — **obowiązkowa figura
„wynik vs. MFW”** (F-18). Wniosek, który znika przy zmianie MFW, nie jest wnioskiem.

## 11. Redukcja wymiarowości przed dystansami i CPD

Przy `n_w ≈ 200` oknach Koranu:
- dla `V` na F1/F3: najpierw MFW/`max_features` cutoff, potem dystans;
  nie stosować PCA przed liczeniem `V` (PCA fitowany na CTRL-TRAIN zmienia
  skalę niesymetrycznie).
- dla CPD i klastrowania: PCA do `min(50, n_w/4)` komponentów, fitowane na
  CTRL-TRAIN, `explained_variance` raportowana.
- UMAP: tylko wizualizacja, nigdy jako wejście do testu statystycznego
  (utrzymane z v1 — słusznie).

## 12. Checklist przed uznaniem rodziny cech za gotową

- [ ] macierz zapisana, z hashem configu i wersją normalizatora/taggera
- [ ] vectorizer fitowany wyłącznie na CTRL-TRAIN (test automatyczny)
- [ ] brak NaN/inf, brak okien z zerowym wektorem
- [ ] rozkład normy wektorów nie koreluje z `n_tokens` (r < 0.3) — jeśli koreluje,
      normalizacja jest zepsuta
- [ ] domain probe (E-01) uruchomiony i zaraportowany
- [ ] figura rozkładu top-K cech dla Koran vs CTRL istnieje
