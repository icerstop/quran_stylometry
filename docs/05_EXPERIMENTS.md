# 05 — Katalog eksperymentów

Format każdego wpisu: **wejście → procedura → metryka → test → kryterium
zaliczenia → figury**. Eksperyment bez kryterium zaliczenia zapisanego *przed*
uruchomieniem nie jest eksperymentem.

---

## E-00 · Sanity danych i statystyki korpusów
**Wejście:** wszystkie korpusy po normalizacji.
**Procedura:** policz tokeny/segmenty/okna, rozkłady długości, pokrycie EQTB,
odsetek nietypowych znaków, `internal_duplication_rate`, skuteczność usuwania
cytatów (z ręcznym audytem 2×100 przypadków).
**Kryterium:** `results/corpus_stats.json` istnieje i zgadza się z niezależnym
przeliczeniem; recall usuwania cytatów oszacowany ręcznie > 0.8.
**Figury:** FIG-01…FIG-06.

---

## E-01 · Domain probe (G2) — **bramka**
**Pytanie:** czy Koran i CTRL są trywialnie rozróżnialne w przestrzeniach,
w których zamierzamy mierzyć styl?
**Procedura:** klasyfikator (LogReg) `corpus ∈ {quran, ctrl}` na oknach,
osobno dla `CHARACTER`, `FUNCTIONAL`, `LEXICAL`, `BASELINE_LIT`;
`GroupKFold` po `book_id`/`surah_id`, klasy zbalansowane.
**Metryka:** ROC-AUC + 20 najsilniejszych cech.
**Interpretacja:**
- AUC < 0.85 → domena akceptowalna;
- 0.85–0.98 → transfer możliwy, ale wszystkie wnioski AV opatrzone ostrzeżeniem;
- \> 0.98 → **transfer AV nieważny dla tej rodziny**; rodzina traci status `core`.
**Kluczowe:** identyczny probe uruchamiany dla par `ctrl-genre-A vs ctrl-genre-B`
(np. tafsīr vs. poezja). Jeśli AUC dla par gatunkowych jest równie wysokie jak
dla Koran-vs-CTRL, to znaczy że mierzysz gatunek. Ta porównawcza liczba jest
najważniejszym pojedynczym wynikiem diagnostycznym w całym projekcie.
**Figury:** FIG-07, FIG-08.

---

## E-02 · Walidacja sygnału autorstwa (AA na CTRL)
**Procedura:** zadanie `X → author_id` na CTRL, `GroupKFold(groups=book_id)`,
5 foldów. Modele: LinearSVC, LogisticRegression, MultinomialNB (tylko dla
count/TF-IDF), LightGBM (dla cech liczbowych), Burrows's Delta (nearest
centroid) jako baseline klasyczny.
**Metryka:** macro-F1 (główna), accuracy, top-3 accuracy, confusion matrix.
**Baseline'y obowiązkowe:** (a) losowy, (b) most-frequent-class,
(c) sama długość dokumentu i średnia długość słowa.
**Kryterium:** macro-F1 istotnie > baseline (c) dla ≥ 3 rodzin cech; jeśli
`FUNCTIONAL` nie ma sygnału autorstwa na CTRL, nie wolno go używać do wniosków
o Koranie.
**Figury:** FIG-09…FIG-12.

---

## E-03 · Wpływ gatunku na AA (nowy)
**Procedura:** powtórz E-02 w dwóch reżimach: (i) train/test w obrębie jednego
gatunku, (ii) cross-genre (trenuj na prozie, testuj na poezji tego samego autora).
**Metryka:** spadek macro-F1 między (i) a (ii).
**Po co:** liczba „ile atrybucji traci na zmianie gatunku” jest niezbędna do
uczciwej interpretacji `V_Quran`. Jeśli AA traci 40 punktów F1 przy zmianie
gatunku, żaden wniosek o Koranie oparty na porównaniu z prozą się nie obroni.
**Figura:** FIG-13.

---

## E-04 · Wrażliwość na MFW i długość okna
**Procedura:** E-02 i `V` liczone dla siatki MFW `{100,300,1000,3000}`
× window `{250,400,800}`.
**Kryterium:** kierunek wniosku stabilny w ≥ 10 z 12 kombinacji.
**Figura:** FIG-14 (heatmapa).

---

## E-05 · **WYNIK GŁÓWNY** — `V` na skali odniesienia
**Procedura:**
1. Zbuduj `V_single` z PSEUDO-BOOK (≥ 60 autorów × B=200 podpróbek).
2. Zbuduj `V_mixture-k` dla k ∈ {2,3,5} oraz wariant `same-genre`.
3. Policz `V_within-surah` (floor) i `V_multivoice` (kolekcje hadisów).
4. Policz `V_Quran` z tym samym `n_w`, długością okna i B.
5. Powtórz dla `CHARACTER`, `FUNCTIONAL`, `LEXICAL`, `BASELINE_LIT`,
   oraz dla obu estymatorów `V_med`, `V_disp`.
**Test:** percentyl `V_Quran` w każdym rozkładzie, z CI z bootstrapu **po
autorach** (nie po oknach, nie po parach — G5). Dodatkowo: pole przekrycia
rozkładów `V_single` i `V_mixture-2` (overlapping coefficient).
**Kryterium/reguła decyzyjna:** dokładnie jak w `02_DESIGN.md §3 RQ1`.
**E-05b — dekompozycja:** jaka część wariancji `V` w rozkładzie kontrolnym
jest wyjaśniana przez `genre`, `death_date`, `n_works`? (model liniowy
mieszany albo prosta ANOVA). Jeśli `genre` wyjaśnia > 30% — pozycja Koranu
musi być raportowana **względem gatunku**, nie względem całej populacji.
**Figury:** FIG-15…FIG-19. FIG-16 (raincloud z pozycją Koranu i wszystkimi
czterema kotwicami) jest figurą tytułową projektu.

---

## E-06 · Trening i kalibracja AV na CTRL
**Procedura:** pary `SAME`/`DIFFERENT` z CTRL-TRAIN. Reprezentacja pary:
`|x_i - x_j|`, `cos(x_i,x_j)`, `x_i ⊙ x_j`, plus dystanse właściwe dla rodziny.
Modele: LogReg, LinearSVC, LightGBM. Split po `author_id`.
**Sampling par — obowiązkowe kontrole:**
- pary `DIFFERENT` dobierane **hard**: ten sam gatunek, ta sama epoka,
  zbliżona długość (bez tego model uczy się gatunku);
- raportowany stosunek SAME:DIFFERENT i strategia próbkowania;
- pary `SAME` z **różnych dzieł** tego samego autora (`same-author, different-book`)
  raportowane osobno od `same-book` — to dwie różne trudności.
**Metryka:** ROC-AUC, PR-AUC, EER, Brier score, krzywa kalibracji.
**Kalibracja:** na CTRL-CALIB (rozłączny zbiór autorów), Platt/isotonic.
**Kryterium:** EER na CTRL-TEST ≤ 0.25 dla ≥ 2 rodzin cech.
**Figury:** FIG-20…FIG-22.

---

## E-07 · **OOD sanity dla AV — eksperyment z prawem weta**
**Pytanie:** co model AV robi ze *znanymi jednoautorskimi* korpusami spoza
domeny treningowej?
**Procedura:** zastosuj zamrożony model AV do par okien z:
(a) dywanu pojedynczego poety, (b) zbioru maqāmāt jednego autora,
(c) autora z epoki poza zakresem treningu, (d) tekstu o odmiennej ortografii
wydania. Dla każdego policz rozkład `P(same)`.
**Metryka:** odsetek par `same-author` sklasyfikowanych jako `different`
przy progu z kalibracji; EER, jeśli da się zbudować pary kontrastowe.
**Kryterium (bramka dla RQ4):** EER ≤ 0.35 i median `P(same)` > próg dla
wszystkich czterech przypadków.
**Jeśli fail:** RQ4 zostaje zamknięte negatywnie na poziomie metody. Nie
uruchamiamy E-08. To jest przewidziany, akceptowalny wynik projektu.
**Figura:** FIG-23.

---

## E-08 · AV na Koranie (warunkowe na E-07)
**Procedura:** zamrożony model → wszystkie pary okien Koranu → rozkład `P(same)`.
Porównanie z rozkładami dla: PSEUDO-BOOK, MIXTURE-2, kotwic z RQ6.
**Test:** permutacyjny z blokowaniem po `surah_id`.
**Interpretacja:** wyłącznie na poziomie rozkładu, nigdy pojedynczej pary
(utrzymane z v1). Dodatkowo mapa cieplna `P(same)` w porządku chronologicznym —
pokazuje, *gdzie* leżą pary niskiego prawdopodobieństwa.
**Figury:** FIG-24, FIG-25.

---

## E-09 · Meccan/Medinan — klasyfikacja z uczciwymi baseline'ami
**Procedura:** `X → {meccan, medinan}` na oknach Koranu,
`GroupKFold(groups=surah_id)` (nie po oknach!).
Modele: LogReg, LinearSVC, LightGBM.
Konfiguracje: `LEXICAL`, `FUNCTIONAL`, `CHARACTER`, `PROSODIC`, `SYNTAX_Q`, `ALL`.
**Baseline'y obowiązkowe (G7):**
1. `mean_verse_length` jako jedyna cecha,
2. `n_verses` + `mean_verse_length`,
3. długość sury.
**Metryka:** macro-F1, ROC-AUC, oraz **Δ względem baseline 1** z CI (bootstrap
po surach).
**Wariant residualny:** powtórz na cechach po wyregresowaniu
`mean_verse_length` (OLS residuals per feature).
**Kryterium:** `FUNCTIONAL` bije baseline 1 o ≥ 0.05 macro-F1 przy rozłącznych CI.
**Analiza wrażliwości:** bez okien `composite=true`, bez sur `composite_flag=1`.
**Figury:** FIG-26…FIG-28.

---

## E-10 · Interpretacja różnic Meccan/Medinan
**Procedura:** współczynniki LogReg (na standaryzowanych cechach), SHAP dla
LightGBM, plus proste porównanie rozkładów top-30 cech.
**Uwaga:** interpretacja tylko dla modelu, który przeszedł kryterium z E-09.
Interpretowanie ważności cech modelu, który nie bije baseline'u długości ajatu,
to opisywanie szumu.
**Figury:** FIG-29, FIG-30.

---

## E-11 · Change-point detection
**Procedura:** `ruptures`, algorytmy **PELT** i **KernelCPD** (dwa, nie cztery).
Sekwencja okien w porządku chronologicznym (trzy uporządkowania z `03_DATA §8`).
Wejście: PCA(≤50) z `FUNCTIONAL`, `CHARACTER`, `SYNTAX_Q`.
Dobór penalty: przez BIC/elbow na danych kontrolnych, **nie** dostrajany do
uzyskania „ładnego” wyniku na Koranie — wartość zamrożona przed FREEZE.
**Testy negatywne (G9), obowiązkowe w tej samej figurze:**
1. przetasowana kolejność okien (CPD nie powinno wykrywać nic ponad losowość),
2. PSEUDO-BOOK w porządku „chronologicznym” dzieł jednego autora,
3. MIXTURE-2 ułożone blokami (CPD powinno znaleźć granicę — test czułości).
**Test:** permutacyjny (10 000 iteracji, blokowanie po surach): odległość
wykrytych punktów od granic historycznych vs. rozkład dla segmentacji losowej.
**Wariant residualny (G7):** to samo po wyregresowaniu `mean_verse_length`.
**Figury:** FIG-31…FIG-33.

---

## E-12 · Unsupervised: PCA / klastrowanie
**Procedura:** PCA, hierarchiczne (Ward), HDBSCAN, GMM z BIC/AIC dla K=1..10.
Etykiety `period` przypisywane **po** klastrowaniu.
**Metryki:** ARI, NMI, purity, silhouette.
**Kontrola obowiązkowa:** te same metryki dla PSEUDO-BOOK i MIXTURE-2 — bez
tego liczba „ARI = 0.31” nie ma skali.
**Uwaga do GMM:** przy ~200 oknach i wysokiej wymiarowości BIC będzie niestabilny;
raportuj krzywą BIC, nie samo argmin, i stosuj na przestrzeni po PCA.
**Figury:** FIG-34, FIG-35.

---

## E-13 · Test „criterion of concurrent smoothness” (baseline literaturowy)
**Procedura:** zaimplementuj kryterium współbieżnej gładkości na markerach F9;
policz je dla: Koranu (3 uporządkowania), PSEUDO-BOOK, MIXTURE-2, MIXTURE-5,
sekwencji losowej.
**Pytanie:** czy kryterium odróżnia korpus jednoautorski od mieszanki, gdy
znamy prawdę? Jeśli MIXTURE też wychodzi „gładka”, kryterium nie ma mocy
diagnostycznej i należy to napisać.
**Figura:** FIG-36.

---

## E-14 · Transformery (eksploracyjne, ścięte)
**Zakres:** jeden model — CAMeLBERT-CA, jeden pooling — mean z 4 ostatnich
warstw. Zadania: `V`, Meccan/Medinan, klastrowanie. Bez AA/AV cross-corpus.
**Obowiązkowy dopisek w każdej figurze:** model pretrenowany na danych typu
OpenITI, które zawierają cytaty koraniczne — kontaminacja prawdopodobna.
**Kryterium raportowania:** wyniki podawane wyłącznie w osobnej sekcji,
oznaczone jako niepotwierdzające wniosków głównych.
**Figura:** FIG-37, FIG-38.

---

## Macierz: eksperyment × reprezentacja (v2, po cięciach)

| | E-01 | E-02 | E-05 | E-06/07/08 | E-09 | E-11 | E-12 |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| CHARACTER (F1) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| FUNCTIONAL (F2,F4,F5,F6) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| LEXICAL (F3) | ✓ | ✓ | ✓ | — | ✓ | — | ✓ |
| PROSODIC (F8) | — | — | — | — | ✓* | ✓* | — |
| SYNTAX_Q (F7) | — | — | — | — | ✓ | ✓ | ✓ |
| BASELINE_LIT (F9) | ✓ | ✓ | ✓ | — | ✓ | ✓ | — |
| CAMeLBERT-CA | — | — | ✓ᵉ | — | ✓ᵉ | ✓ᵉ | ✓ᵉ |

`*` = status `circular`, nie uzasadnia wniosku samodzielnie.
`ᵉ` = eksploracyjne, E-14.

Liczba głównych przebiegów spadła z ~200 (v1) do ~45.
