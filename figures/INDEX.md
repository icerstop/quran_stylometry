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
