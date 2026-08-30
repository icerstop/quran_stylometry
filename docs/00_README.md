# Quran Stylometry & Authorship Verification — plan v2

Zestaw dokumentów zastępujący pierwotny plan. Powstał po krytycznej recenzji;
zmiany nie są kosmetyczne — zmienia się **estymand**, **zbiór kontrolny**,
**pipeline anotacji** i **zakres**.

## Jak czytać

| Plik | Zawartość | Dla kogo |
|---|---|---|
| `AGENTS.md` | **Punkt wejścia agenta**: zasady twarde, kiedy się zatrzymać | Agent (czyta pierwszy) |
| `09_DECISIONS.md` | **Wszystkie decyzje zamknięte**: narzędzia, źródła, selekcja, gatunki, parametry | Agent (wiążące) |
| `10_COMPUTE.md` | Podział laptop / klaster, skrypty SLURM, fallback bez klastra | Ty + agent |
| `11_HANDOFF.md` | Protokół przekazania zadań na klaster, checklista przed `sbatch` | Ty + agent |
| `data_reference/chronologies.csv` | Gotowa chronologia 114 sur + wyjątki wersetowe | dane |
| `01_REVIEW.md` | Krytyka planu v1: 22 findings z severity, co blokuje publikowalność | Ty (decyzje) |
| `02_DESIGN.md` | Poprawiony design badawczy: estymandy, hipotezy, reguły decyzyjne, pre-registration | Ty + agent |
| `03_DATA.md` | Źródła, licencje, normalizacja, anotacja, segmentacja, schemat danych | Agent |
| `04_FEATURES.md` | Rodziny cech F1–F9, polityka fitowania, anty-leakage | Agent |
| `05_EXPERIMENTS.md` | E00–E14: wejście, wyjście, metryka, test statystyczny, kryterium zaliczenia | Agent |
| `06_FIGURES.md` | Katalog 38 figur + dashboard; każda z pełną specyfikacją | Agent |
| `07_TASKS.md` | Backlog T-001…T-052 z Definition of Done i zależnościami | Agent |
| `08_REPO.md` | Struktura repo, configi, determinizm, testy, budżet obliczeniowy | Agent |

Kolejność implementacji: `07_TASKS.md` jest jedynym źródłem prawdy o kolejności.

## Co się zmieniło względem v1 — skrót

1. **Dwa rozkłady odniesienia zamiast jednego.** v1 liczył percentyl Koranu w
   rozkładzie korpusów jednoautorskich. To test jednostronny bez alternatywy —
   nie rozróżnia hipotez. v2 buduje także rozkład **sztucznych korpusów
   wieloautorskich** (k = 2, 3, 5) i lokalizuje Koran między dwoma rozkładami.
2. **Symetria anotacji jest twarda.** v1 dawał Koranowi złote tagi QAC, a OpenITI
   tagi z taggera MSA. To gwarantowany artefakt. v2: **ten sam tagger po obu
   stronach**; złote tagi QAC służą wyłącznie do pomiaru błędu taggera.
3. **Ortografia ujednolicona.** Ortografia uthmani vs. imlāʾī rozjeżdża character
   n-gramy w sposób, który udaje sygnał stylu. v2 używa warstwy imlāʾī z EQTB
   i tego samego normalizatora po obu stronach + probe domenowy.
4. **Kontrole dobrane po gatunku, nie tylko po rozmiarze.** Pseudo-book control
   z v1 kontroluje wielkość korpusu, nie rejestr. Dochodzą kotwice:
   maqāmāt (saʿ), dywany poetyckie, zbiory duʿāʾ, oraz **teksty jawnie
   wielogłosowe** (kolekcje hadisów) jako górna kotwica heterogeniczności.
5. **Kluczowy nowy eksperyment: OOD-sanity dla AV** (E-07). Model AV trenowany na
   prozie OpenITI jest stosowany do *znanych jednoautorskich* tekstów spoza
   domeny. Jeśli i one dostają „different-author”, wynik dla Koranu jest pusty.
   Ten eksperyment ma prawo unieważnić RQ4.
6. **Statystyka naprawiona.** Mann–Whitney na dystansach parowych jest nieważny
   (obserwacje zależne). Inferencja idzie po **autorach i surach**, nie po oknach.
7. **Okna nie przekraczają granic sury ani dzieła.**
8. **Chronologia jest zmienną, nie faktem.** Trzy niezależne rekonstrukcje jako
   analiza wrażliwości + jawne potraktowanie cyrkularności (chronologia była
   budowana m.in. na długości ajatów, czyli na cechach stylometrycznych).
9. **Baseline z literatury.** Sadeghi (Arabica 58/2011) i krytyka jego „criterion
   of concurrent smoothness” są punktem odniesienia, nie tłem.
10. **Zakres ścięty ~40%.** Transformery: jeden model, status eksploracyjny.
    Składnia: tylko wewnątrz Koranu. Cztery algorytmy CPD → dwa.

## Minimalny wynik obronny (MDR)

Projekt uznajemy za udany, jeśli powstanie **wyłącznie** to:

- E-02 (walidacja sygnału autorstwa na OpenITI) — macro-F1 istotnie > baseline,
- E-05 (V_Koranu vs. rozkład jednoautorski **i** wieloautorski, ≥ 60 autorów),
- E-07 (OOD-sanity) — z uczciwym raportem, także jeśli unieważnia AV,
- E-09 (Meccan/Medinan vs. baseline „sama długość ajatu”),
- pakiet figur A + D + rozdział „Threats to validity”.

Wszystko poza tym jest opcjonalne i nie może opóźnić MDR.

## Zasada nadrzędna interpretacji

Utrzymana z v1 i wzmocniona: żaden wynik nie jest dowodem jednego lub wielu
autorów. Raportujemy **położenie mierzonego sygnału językowego względem jawnie
zdefiniowanych korpusów odniesienia**, wraz z listą konfundów, których nie
udało się usunąć. Każde zdanie w `reports/` musi dać się przepisać do postaci:
„miara M w reprezentacji R, przy kontrolach C, plasuje Koran na percentylu P
rozkładu korpusów typu T”.

## Słownik terminów używanych w tych plikach

- **CORPUS_CTRL** — korpus kontrolny OpenITI po czyszczeniu.
- **PSEUDO-BOOK** — sztuczny korpus jednego autora o wielkości Koranu.
- **MIXTURE** — sztuczny korpus z k autorów o wielkości Koranu.
- **V_X** — miara wewnętrznej zmienności stylistycznej korpusu X (def. w `02_DESIGN.md`).
- **GUARDRAIL (G1–G9)** — obowiązkowe zabezpieczenie metodologiczne; naruszenie = wynik nie idzie do raportu.
- **FREEZE** — moment zamrożenia decyzji analitycznych przed dotknięciem danych Koranu.
