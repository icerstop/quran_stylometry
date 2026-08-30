# SOURCES.md — odniesienia bibliograficzne z numerami stron

Ten plik wypelniaja zadania **T-018** (chronologia) i **T-028** (lista markerow F9).
W fazie P0 powstaje wylacznie szkielet, zeby bylo widac, czego jeszcze brakuje.

Zasada: kazde odniesienie ma numer strony albo dokladny adres. "Za literatura"
bez wskazania miejsca nie jest odniesieniem.

---

## 1. Chronologia sur (T-018)

- **Tanzil, Revelation Order** — <https://tanzil.net/docs/revelation_order>.
  Zrodlo kolumn `order_traditional` i `period_traditional`
  w `data/reference/chronologies.csv`. Oparta na al-Zanjanim / Ibn 'Abbasie.
  *Status: uzyte, zweryfikowane programowo 2026-08-30.*
- **Noldeke** — `order_noldeke` wyliczony deterministycznie z porzadku
  tradycyjnego przez dwie udokumentowane zmiany: sura 110 przenoszona miedzy
  59 a 24; sura 62 przed 64 i 61.
  *Do uzupelnienia w T-018: odniesienie stronicowe do* Geschichte des Qorāns.
- **Sadeghi, Arabica 58 (2011)** — **NIEDOSTEPNE ZA DARMO (paywall)**.
  `order_sadeghi` zostalo **usuniete z designu** (`09_DECISIONS.md` §2.4).
  Nie zastepujemy go zgadywanym uporzadkowaniem.
- **Blachere** — **NIEDOSTEPNE ZA DARMO (paywall)**. Nie uzywane.

**Ograniczenie do zaraportowania (09_DECISIONS.md §2.4):** `order_traditional`
i `order_noldeke` roznia sie pozycja tylko dla 13 sur, wiec Spearman rho ~ 0,99.
To **nie jest** mocna analiza wrazliwosci i tak ma byc opisane. Prawdziwy
kontrast to `order_canonical` vs `order_traditional`; najmocniejsza kontrola to
relabeling wersetowy z `exception_verses`.

## 2. Markery baseline'u literaturowego F9 (T-028)

*Do uzupelnienia w T-028.* Wymagane: skad dokladnie wzieto liste czestych
morfemow uzytych jako markery, i jak zdefiniowano operacyjnie kryterium
"concurrent smoothness".

**Adnotacja obowiazkowa do raportu (09_DECISIONS.md §2.4):** F9 jest
**rekonstrukcja rodziny markerow**, nie odtworzeniem konkretnej pracy — tekst
zrodlowy jest za paywallem.

## 3. Krytyka kryterium "concurrent smoothness" (T-047 / E-13)

*Do uzupelnienia.* Odniesienie do opublikowanej krytyki kryterium, wobec ktorej
E-13 jest bezposrednia odpowiedzia.

## 4. Zasoby danych

Pelne warunki uzycia, wersje i daty pobrania: `DATA_LICENSES.md`.
Odczyt maszynowy: `results/source_check.json` (`make verify-sources`).
