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

### Pole niepewne u zrodla: `constituent_node` (EQTB)

`docs/09_DECISIONS.md` §2.1 wymienia `constituent_node` jako jedna z 42
oczekiwanych kolumn tabeli tokenowej EQTB (`corpus/Quranic.rar` ->
`Quranic.csv`). Kolumna ta **nie wystepuje pod ta nazwa w zrodle**.

README repozytorium `NoorBayan/Quranic` samo sygnalizuje niejednoznacznosc
tego pola dopiskiem (parafraza): *"previously classification of binary
constituent relations, might need clarification or renaming based on your
exact schema"* — czyli autorzy zrodla sami nie sa pewni aktualnej nazwy/definicji.

Sprawdzone dowody (dochodzenie w `scripts/probe_eqtb_archive.py`, probka 20000
wierszy z `Quranic.csv`):
- `head_rel` jest jedynym polem faktycznie **binarnym**: `{0: 19946, 1: 53}`
  — zgodne z opisem "binary constituent relations", ale to poszlaka, nie
  potwierdzenie ze strony zrodla.
- `depend_rel` odpada jako kandydat: ma trzy wartosci (`-1`, `0`, `1`), nie dwie.

**Decyzja (`docs/09_DECISIONS.md` §2.1, 2026-08-30): NIE rozstrzygac.**
`constituent_node` zostaje nullable/`unmapped` w schemacie `Window`
(`configs/sources.yaml` -> `unresolved_columns`), bo zadna rodzina cech
w `docs/04_FEATURES.md` §F7 nie korzysta z pol `constituent_*` — skladnia
w tym projekcie opiera sie wylacznie na `rel_label` i `ref_token_id`. Jesli
przyszly eksperyment kiedykolwiek bedzie potrzebowal tego pola, rozstrzygniecie
ma zapadac wtedy, z konkretnym kontekstem uzycia — nie na sucho, w T-009.

Dla porownania, `constituent_position` **zostalo rozstrzygniete**: w zrodle
nazywa sie `constituents_loc` (format `[start-end]`, dokladnie zgodny z opisem
README "start and end token IDs defining the span"), mapowane 1:1 w
`src/data/download_eqtb.py`.
