# INDEX figur

Rejestr generowany automatycznie przez `src.viz.save.save_fig`. Nie edytuj recznie
— kazdy wpis powstaje razem z plikami PNG/SVG/JSON i znika, gdy figura zniknie.

Kazdy wpis odpowiada na cztery pytania z `docs/06_FIGURES.md`: co pokazuje, jak
czytac, czego **nie** wolno wnioskowac, i jaka kotwice kontrolna niesie (G9).

<!-- fig:FIG-00 -->
## FIG-00 — smoke_test

- Eksperyment: none
- Typ: result
- Rodziny cech: synthetic
- Kotwica kontrolna (G9): synthetic_shuffle (rozklad odniesienia w tym samym panelu)
- Pokazuje: Figura testowa warstwy src/viz: dwa syntetyczne rozklady i pionowa linia obserwacji, w ukladzie identycznym jak FIG-15/FIG-16.
- Jak czytac: Sprawdz, ze istnieja PNG, SVG i JSON o tym samym rdzeniu nazwy, oraz ten wpis w INDEX.md. Nie odczytuj z niej niczego o korpusach.
- Czego NIE wolno wnioskowac: Nie wolno wyciagac z niej ZADNEGO wniosku merytorycznego. Dane sa losowe, wygenerowane z seeda configu, i nie pochodza z zadnego korpusu.
- Pliki: `FIG-00_smoke_test.png`, `FIG-00_smoke_test.svg`, `FIG-00_smoke_test.json`
<!-- /fig:FIG-00 -->

<!-- fig:FIG-39 -->
## FIG-39 — tagger_eval

- Eksperyment: T-014
- Typ: diagnostic
- Rodziny cech: pos, morph
- Kotwica kontrolna (G9): majority-class baseline na warstwie coarse POS (najczestszy tag gold EQTB, ta sama liczba tokenow)
- Pokazuje: Accuracy POS CAMeL Tools (calima-msa-r13, MLE) wobec gold EQTB per kubelek coarse, obok linii majority baseline.
- Jak czytac: Slupek = udzial poprawnych tagow coarse w danym kubełku. Pionowa linia = accuracy, gdyby tagger zawsze zwracal najczestszy tag gold. Fine POS i lemat sa w JSON-ie figury / results/tagger_eval.json, nie na osi.
- Czego NIE wolno wnioskowac: Nie wnioskuj z tej figury o autorstwie Koranu ani o jakosci tagowania CTRL. Referencja to EQTB (fallback T-010), nie QAC. CAMeL jest MSA, nie Quranic-specific.
- Pliki: `FIG-39_tagger_eval.png`, `FIG-39_tagger_eval.svg`, `FIG-39_tagger_eval.json`
<!-- /fig:FIG-39 -->

<!-- fig:FIG-05 -->
## FIG-05 — quote_removal

- Eksperyment: T-016
- Typ: result
- Rodziny cech: quotes
- Kotwica kontrolna (G9): shuffle: 7-gramy z permutacji tokenow Koranu (ten sam slownik i n, bez ciaglosci cytatu); usuniecie z CTRL przy identycznym marginesie ±3
- Pokazuje: Per gatunek CTRL: tokeny RAW, tokeny wykryte jako cytat (7-gramy), tokeny usuniete po marginesie ±3, oraz usuniecie na indeksie shuffle.
- Jak czytac: Wysoki slupek usunietych przy niskim shuffle znaczy, ze wycinamy ciagi z Koranu, nie losowe zbitki. Tafsir moze tracic 30–50% objetosci — to oczekiwane (03_DATA.md §7a), nie blad.
- Czego NIE wolno wnioskowac: Nie wnioskuj o autorstwie Koranu. Precyzja/recall sa z recznego audytu 2×100, nie z tej figury. Shuffle to kontrola struktury, nie p-wartosc.
- Pliki: `FIG-05_quote_removal.png`, `FIG-05_quote_removal.svg`, `FIG-05_quote_removal.json`
<!-- /fig:FIG-05 -->

<!-- fig:FIG-06 -->
## FIG-06 — internal_duplication

- Eksperyment: T-017
- Typ: result
- Rodziny cech: duplication
- Kotwica kontrolna (G9): shuffle: permutacja tokenów w obrębie sury (Koran) / dzieła (CTRL), ten sam n=7; wąsy = SD po jednostkach
- Pokazuje: Odsetek typów 7-gramów występujących ≥ 2 razy: Koran, CTRL łącznie i per gatunek, obok shuffle.
- Jak czytac: Wysoki raw przy niskim shuffle = powtórzenia sekwencji (formuła, refren), nie sam rozkład częstości słów. Wariant dedup jest w JSON.
- Czego NIE wolno wnioskowac: Nie wnioskuj o autorstwie Koranu. To diagnostyka korpusu (F-11), nie V. T-041 (kotwice RQ6) jeszcze nie istnieje — nie ma ich na figurze.
- Pliki: `FIG-06_internal_duplication.png`, `FIG-06_internal_duplication.svg`, `FIG-06_internal_duplication.json`
<!-- /fig:FIG-06 -->

<!-- fig:FIG-06b -->
## FIG-06b — chronology_agreement

- Eksperyment: T-018
- Typ: result
- Rodziny cech: chronology
- Kotwica kontrolna (G9): shuffle: Spearman ρ(order_canonical, permutacja order_traditional); n_perm i momenty w JSON. Oczekiwane ~0.
- Pokazuje: Macierz Spearman ρ: order_canonical, order_traditional, order_noldeke (114 sur). Sadeghi nieobecny.
- Jak czytac: ρ(traditional, noldeke) bliskie 1: dwie edycje Tanzila, nie niezależna chronologia. Kontrast to canonical vs traditional. Shuffle ~0 pokazuje, że wysokie ρ nie wynika z samego faktu, że obie listy mają 114 rang.
- Czego NIE wolno wnioskowac: Nie wnioskuj o datowaniu sur ze stylu (F-08). Nie traktuj Nöldekego jako trzeciej niezależnej osi — Sadeghi/Blachère odpadły (paywall). FIG-06b nie jest wynikiem V.
- Pliki: `FIG-06b_chronology_agreement.png`, `FIG-06b_chronology_agreement.svg`, `FIG-06b_chronology_agreement.json`
<!-- /fig:FIG-06b -->

<!-- fig:FIG-40 -->
## FIG-40 — character_topk

- Eksperyment: T-021
- Typ: result
- Rodziny cech: character
- Kotwica kontrolna (G9): CTRL-TEST: te same cechy TF-IDF, autorzy niewidziani przy fitowaniu (G4). Quran i TRAIN w tym samym panelu.
- Pokazuje: Top-20 n-gramow znakowych (char_wb 3–5) wg sredniego TF-IDF na CTRL-TRAIN, obok srednich na CTRL-TEST i Koranie.
- Jak czytac: Jesli slupki TRAIN i TEST sa bliskie, cecha generalizuje poza autorow treningowych. Duza luka Koran vs TEST to sygnal domeny (E-01), nie V.
- Czego NIE wolno wnioskowac: Nie wnioskuj o autorstwie Koranu. To diagnostyka F1 przed E-01. Wariant bez ligatur jest w JSON-ie, nie na tej osi.
- Pliki: `FIG-40_character_topk.png`, `FIG-40_character_topk.svg`, `FIG-40_character_topk.json`
<!-- /fig:FIG-40 -->

<!-- fig:FIG-41 -->
## FIG-41 — function_topk

- Eksperyment: T-022
- Typ: result
- Rodziny cech: function_words
- Kotwica kontrolna (G9): CTRL-TEST: te same K function words, autorzy niewidziani przy fitowaniu (G4). Quran i TRAIN w tym samym panelu.
- Pokazuje: Top-20 form funkcyjnych (POS whitelist, segmenty morfologiczne) wg sredniej czestosci wzglednej na CTRL-TRAIN, obok CTRL-TEST i Koranu.
- Jak czytac: Jesli slupki TRAIN i TEST sa bliskie, cecha generalizuje poza autorow treningowych. Duza luka Koran vs TEST to sygnal domeny (E-01), nie V.
- Czego NIE wolno wnioskowac: Nie wnioskuj o autorstwie Koranu. To diagnostyka F2 przed E-01. Siatka K jest w JSON-ie (100/300/1000), nie na tej osi.
- Pliki: `FIG-41_function_topk.png`, `FIG-41_function_topk.svg`, `FIG-41_function_topk.json`
<!-- /fig:FIG-41 -->

<!-- fig:FIG-42 -->
## FIG-42 — lexical_topk

- Eksperyment: T-023
- Typ: result
- Rodziny cech: lexical
- Kotwica kontrolna (G9): CTRL-TEST: te same cechy TF-IDF (word 1–2 gram), autorzy niewidziani przy fitowaniu (G4). Quran i TRAIN w tym samym panelu.
- Pokazuje: Top-20 cech leksykalnych (word 1–2 gram, TF-IDF) wg sredniego TF-IDF na CTRL-TRAIN, obok srednich na CTRL-TEST i Koranie.
- Jak czytac: Duza luka Koran vs TEST to gorna granica wycieku tematu (F3=support), nie V. TRAIN≈TEST znaczy, ze slownik generalizuje poza autorow treningu.
- Czego NIE wolno wnioskowac: Nie uzasadniaj wnioskiem o autorstwie ani chronologii. F3 jest support: merzy wyciek tematu. Lemma/root sa w JSON-ie, nie na tej osi.
- Pliki: `FIG-42_lexical_topk.png`, `FIG-42_lexical_topk.svg`, `FIG-42_lexical_topk.json`
<!-- /fig:FIG-42 -->
