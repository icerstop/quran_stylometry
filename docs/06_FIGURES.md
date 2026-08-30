# 06 — Katalog figur i wizualizacji

## Zasady wspólne

- Jedna figura = jeden plik `figures/FIG-XX_<slug>.{png,svg}` + `.json`
  z danymi źródłowymi + wpis w `figures/INDEX.md` (ID, eksperyment, co pokazuje,
  jak czytać, jakich wniosków **nie** wolno z niej wyciągać).
- Każdy wykres generowany funkcją `make_fig_XX(...)` w `src/viz/`, wołaną ze
  skryptu, nigdy z notebooka bez zapisu.
- Paleta zgodna z daltonizmem (`viridis`/`cividis` dla map ciepła,
  Okabe–Ito dla kategorii). Zero czerwony-zielony jako jedyny kontrast.
- **Każda figura z wynikiem ma w tym samym panelu odniesienie kontrolne**
  (G9): shuffle, mixture, pseudo-book albo baseline. Figura bez kotwicy nie
  wchodzi do raportu.
- Przedziały ufności zawsze widoczne. Jeśli CI nie da się policzyć — napisz to
  na figurze.
- Skala osi `V` identyczna we wszystkich figurach porównujących `V`.

---

## A · Dane i EDA

| ID | Typ | Zawartość |
|---|---|---|
| FIG-01 | histogram + rug | Rozkład długości sur (słowa, ajaty) w skali log; zaznaczony próg okna 400 |
| FIG-02 | histogram nakładany | Długość ajatu w Koranie vs. długość zdania w CTRL wg gatunku |
| FIG-03 | bar h | Liczba tokenów i dzieł na autora CTRL (posortowane), linia progu selekcji |
| FIG-04 | scatter | `death_date` × liczba tokenów; kolor = gatunek; pokazuje pokrycie chronologiczne |
| FIG-05 | waterfall | Skuteczność usuwania cytatów koranicznych: tokeny RAW → wykryte → usunięte, per gatunek |
| FIG-06 | bar + błąd | `internal_duplication_rate` dla Koranu, gatunków CTRL i kotwic |
| FIG-06b | macierz | Zgodność uporządkowań chronologicznych (Spearman ρ: cairo / Nöldeke / Sadeghi) |

## B · Bramka domenowa i walidacja

| ID | Typ | Zawartość |
|---|---|---|
| FIG-07 | grouped bar | **AUC domain probe**: `Koran vs CTRL` obok `gatunek A vs gatunek B` dla każdej rodziny cech. Kluczowa figura diagnostyczna — jeśli słupki są podobnej wysokości, mierzysz gatunek |
| FIG-08 | bar poziomy | Top-20 cech napędzających probe (z kierunkiem), rodzina CHARACTER i FUNCTIONAL |
| FIG-09 | box + punkty | macro-F1 AA per rodzina cech × model, z baseline'ami (losowy, długość) |
| FIG-10 | heatmapa | Confusion matrix najlepszego modelu AA (autorzy posortowani po epoce) |
| FIG-11 | krzywa | Top-k accuracy (k=1..10) dla trzech najlepszych konfiguracji |
| FIG-12 | scatter | macro-F1 vs. liczba tokenów na autora — czy sygnał to tylko efekt wielkości? |
| FIG-13 | slope chart | AA within-genre → cross-genre, linia na autora; pokazuje koszt zmiany gatunku |
| FIG-14 | heatmapa | Wrażliwość: MFW × długość okna → macro-F1 (i osobno → percentyl `V_Quran`) |

## C · Wynik główny — `V` na skali

| ID | Typ | Zawartość |
|---|---|---|
| **FIG-15** | **raincloud / ridgeline** | **Figura tytułowa.** Rozkłady `V_single`, `V_mixture-2/3/5`, `V_multivoice`; pionowa linia = `V_Quran` z CI; poziomy pasek = `V_within-surah` (floor). Osobny panel na rodzinę cech |
| FIG-16 | forest plot | Percentyl `V_Quran` w `V_single` i w `V_mixture-2`, z CI, dla każdej rodziny cech i obu estymatorów — jedna figura, cały wynik główny |
| FIG-17 | ECDF | Dystrybuanty `V_single` i `V_mixture-2` z zaznaczonym polem przekrycia (overlapping coefficient) — pokazuje moc metody |
| FIG-18 | box wg gatunku | `V_single` rozbite na gatunki (E-05b); pozycja Koranu względem każdego gatunku osobno |
| FIG-19 | bar | Dekompozycja wariancji `V` w CTRL: udział `genre`, `death_date`, `n_works`, reszta |
| FIG-19b | ECDF nakładane | Rozkłady dystansów `within-book`, `within-author`, `between-author`, `Quran` — **opisowo, bez p-wartości** (F-06) |

## D · Authorship Verification

| ID | Typ | Zawartość |
|---|---|---|
| FIG-20 | ROC + PR | AV na CTRL-TEST, per rodzina cech; zaznaczony EER |
| FIG-21 | reliability diagram | Kalibracja `P(same)` na CTRL-CALIB i CTRL-TEST |
| FIG-22 | dwa histogramy | `P(same)` dla par `same-book`, `same-author-different-book`, `different-author` |
| **FIG-23** | **dot plot + rozkłady** | **OOD sanity (E-07).** `P(same)` dla znanych korpusów jednoautorskich spoza domeny: dywan, maqāmāt, inna epoka, inna ortografia. Z progiem kalibracyjnym. Ta figura decyduje, czy RQ4 w ogóle żyje |
| FIG-24 | ridgeline | `P(same)` dla par Koranu vs. PSEUDO-BOOK vs. MIXTURE-2 vs. kotwice RQ6 |
| FIG-25 | heatmapa trójkątna | `P(same)` dla wszystkich par okien Koranu, uporządkowanych chronologicznie; adnotacja granic okresów |

## E · Chronologia i Meccan/Medinan

| ID | Typ | Zawartość |
|---|---|---|
| FIG-26 | grouped bar + CI | macro-F1 Meccan/Medinan per konfiguracja cech, z trzema baseline'ami długości; **Δ wobec baseline'u jako druga oś** |
| FIG-27 | side-by-side | Ten sam wykres na cechach surowych vs. po wyregresowaniu `mean_verse_length` |
| FIG-28 | bar | Analiza wrażliwości: pełny zbiór / bez okien kompozytowych / bez sur `composite_flag` |
| FIG-29 | lollipop dwustronny | Współczynniki LogReg (top 25 w każdą stronę), cechy nazwane po ludzku |
| FIG-30 | beeswarm SHAP | Ważność cech LightGBM (tylko jeśli model przeszedł kryterium E-09) |
| FIG-30b | line + wstęga | Trajektoria wybranych markerów F9 wzdłuż trzech uporządkowań chronologicznych (test „smoothness” wizualnie) |

## F · Change points

| ID | Typ | Zawartość |
|---|---|---|
| FIG-31 | seria czasowa + pionowe linie | Sygnał stylistyczny (PC1–PC3) wzdłuż chronologii, wykryte change pointy, granice historyczne |
| FIG-32 | panel 4× | Ta sama analiza dla: Koran / Koran-shuffle / PSEUDO-BOOK / MIXTURE-2-blokowa. Test negatywny i test czułości obok wyniku (G9) |
| FIG-33 | histogram + linia | Rozkład permutacyjny statystyki dopasowania change pointów do granic historycznych; obserwowana wartość |

## G · Unsupervised

| ID | Typ | Zawartość |
|---|---|---|
| FIG-34 | scatter 2×2 | PCA i UMAP okien Koranu; kolor = okres, kształt = kompozytowe; obok ten sam rzut dla PSEUDO-BOOK i MIXTURE-2 |
| FIG-35 | bar + krzywa | ARI/NMI/purity dla klastrowania Koranu vs. te same metryki dla korpusów kontrolnych; krzywa BIC dla GMM |
| FIG-36 | multi-line | „Concurrent smoothness” dla Koranu, mieszanek i sekwencji losowej — czy kryterium ma moc dyskryminacyjną (E-13) |

## H · Transformery (eksploracyjne)

| ID | Typ | Zawartość |
|---|---|---|
| FIG-37 | scatter + box | `V` z embeddingów CAMeLBERT-CA na tle skali z FIG-15; wyraźna adnotacja o kontaminacji |
| FIG-38 | scatter porównawczy | Zgodność wyników neuronowych i klasycznych: percentyl `V_Quran` (klasyczne) vs. (neuronowe), punkt na rodzinę cech |

---

## Dashboard końcowy

`reports/dashboard.html` — pojedynczy samodzielny plik HTML (bez zależności
sieciowych), sekcje:

1. **Nagłówek wyników** — 4 kafle: percentyl w `V_single`, percentyl
   w `V_mixture-2`, wynik bramki E-01, wynik bramki E-07 (pass/fail).
2. **Wynik główny** — FIG-15, FIG-16, FIG-17 z przełącznikiem rodziny cech.
3. **Bramki i kontrole** — FIG-07, FIG-23, FIG-32 (testy negatywne).
4. **Chronologia** — FIG-26, FIG-27, FIG-31.
5. **Threats to validity** — tabela z `02_DESIGN.md §6`, każdy wiersz linkuje
   do figury, która go kwantyfikuje.
6. **Deviations from preregistration** — automatycznie generowana z diffa
   configu wobec `configs/frozen/`.

Wymóg: dashboard budowany skryptem `make dashboard`, dane wczytywane
z `results/*.json`, żadnych liczb wpisanych ręcznie w HTML.

---

## Antywzorce, których nie robimy

- Wykres UMAP jako argument („widać dwa klastry”) — UMAP tylko ilustruje.
- Wykres bez kotwicy kontrolnej.
- Wykres percentyla bez CI.
- Confusion matrix bez informacji o liczności klas.
- Ten sam wynik pokazany trzy razy w trzech formach, żeby wypełnić raport.
- Osie ucięte tak, że różnica 0.02 wygląda jak przepaść.
