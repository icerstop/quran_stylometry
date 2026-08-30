# DATA_LICENSES.md — licencje i proweniencja danych (T-003)

Podstawa: `docs/09_DECISIONS.md` §7. Licencje w kolumnie **zaobserwowana** zostaly
odczytane programowo ze zrodla (GitHub API, Zenodo API, strona pobierania), a nie
przepisane z dokumentacji — AGENTS.md zasada 8. Aktualny odczyt maszynowy zyje
w `results/source_check.json` i jest odswiezany przez `make verify-sources`.

Data weryfikacji: **2026-08-30**.

**Zasada dla repo (09_DECISIONS.md §7):** commitujemy kod, configi, manifesty,
hashe i wyniki. Nie commitujemy tekstow zrodlowych. `data/` jest w `.gitignore`
poza `data/reference/`.

---

## 1. EQTB — Extended Quranic Treebank

- Zasob: repozytorium `NoorBayan/Quranic`, katalog `corpus/`
- URL: <https://github.com/NoorBayan/Quranic>
- Licencja deklarowana w `09_DECISIONS.md` §7: **MIT**
- Licencja zaobserwowana (GitHub API, `license.spdx_id`): **MIT** — zgodna
- Konsekwencja: pelna swoboda uzycia, **wymaga atrybucji**
- Rola: podstawowe zrodlo tekstu Koranu; wejscie do pipeline'u to kolumna
  `imlaai_token` (G2), ortografia uthmani wylacznie do kontroli wrazliwosci
- Uwaga metodologiczna: warstwa skladniowa jest czesciowo generowana parserem
  BiLSTM. Traktujemy ja jako **silver**, oznaczamy w metadanych i nie nazywamy gold

> **Rozbieznosc formatu — rozstrzygnieta 2026-08-30.** `Quran.csv`
> (UTF-16-LE, TAB, **5 kolumn**: `aid, chapter, verse, ayah, jmlh`) jest tabela
> na poziomie ajatu i NIE jest uzywany do budowy `Window`. Tabela tokenowa
> lezy w `corpus/Quranic.rar` -> `Quranic.csv` (51 kolumn); 40/42 kolumn
> z `09_DECISIONS.md` §2.1 wystepuje werbatim po zmapowaniu
> `constituents_loc` -> `constituent_position`. `constituent_node` zostaje
> swiadomie nierozstrzygniete (nullable) — patrz `SOURCES.md` §4 i
> `DEVIATIONS.md` D-05. Oba wpisy w `results/blockers.jsonl` sa domkniete
> (`resolved: true`, nie usuniete). Pobranie i parsowanie: `T-009`
> (`src/data/download_eqtb.py`; `n_surahs=114` zweryfikowane programowo,
> `results/corpus_stats.json`). Nie zmienia to statusu licencji.

## 2. QAC — Quranic Arabic Corpus (morfologia)

- Zasob: plik morfologii `quranic-corpus-morphology-*.txt`
- URL: <https://corpus.quran.com/download/>
- Licencja deklarowana w `09_DECISIONS.md` §7: GPL-owy model licencyjny corpus.quran.com
- Licencja zaobserwowana (strona pobierania): **GNU General Public License**,
  Copyright (C) 2011 Kais Dukes — zgodna
- Warunki wprost ze strony: wolno kopiowac i rozpowszechniac kopie *verbatim*;
  **zmienianie pliku jest zabronione**; wymagane wskazanie zrodla i link do
  <http://corpus.quran.com>
- Konsekwencja: uzywane **wylacznie do ewaluacji taggera** (T-014).
  **Nie redystrybuujemy** pliku w repo
- Krok reczny: pobranie wymaga podania adresu e-mail w formularzu. Nie obchodzimy
  tego (AGENTS.md zasada 9) — formularz **nigdy nie zostanie uzyty** (T-010,
  2026-08-30; koliduje z "bez rejestracji" i z odtwarzalnoscia T-051)
- Fallback (dozwolony, formalnie aktywny, nie blocker — `09_DECISIONS.md` §2.2):
  ewaluacja taggera (T-014) odbywa sie wobec kolumn morfologicznych EQTB
  (`data/interim/eqtb_tokens.parquet`, T-009), z adnotacja w raporcie, ze
  referencja jest EQTB, a nie QAC. Zrodlo ma w raporcie status
  `fallback_active` (sformalizowany stan koncowy), **nie** `degraded`
  (co oznaczaloby problem czekajacy na naprawe). Szczegoly: `SOURCES.md` §4.

## 3. OpenITI RELEASE — korpus kontrolny CTRL

- Zasob: release na Zenodo, concept DOI <https://doi.org/10.5281/zenodo.3082463>
- Wersja rozwiazana 2026-08-30: **2025.1.9**, rekord `17767721`,
  DOI wersji `10.5281/zenodo.17767721`, data publikacji 2025-12-30
- Plik metadanych: `OpenITI_metadata_2025-1-9.tsv` (12 092 756 B,
  md5 `cb2226f64264efa964df9ef659d40199`)
- Licencja deklarowana w `09_DECISIONS.md` §7: "open access, teksty z Shamela/JK
  o roznym pochodzeniu"
- Licencja zaobserwowana (Zenodo API, `metadata.license.id`): **`cc-by-nc-sa-4.0`**

> **Do decyzji czlowieka, zgloszone i nie rozstrzygniete samodzielnie.**
> CC-BY-NC-SA-4.0 to wiecej niz "open access": klauzula **NC** (niekomercyjne)
> i **SA** (na tych samych warunkach) moga dotyczyc sposobu publikacji wynikow
> i ewentualnej redystrybucji artefaktow pochodnych. Dla samego badania
> naukowego uzycie jest w porzadku. Zapisano fakt zmierzony; `docs/` nie ruszano.

- Konsekwencja praktyczna (bez zmian): **nie redystrybuujemy tekstow w repo**;
  commitujemy wylacznie manifest i hashe
- Pobieranie: najpierw sam plik metadanych TSV, potem selektywnie ~80 plikow przez
  `raw.githubusercontent.com` z repozytoriow 25-letnich (`OpenITI/0525AH` itd.).
  **Nigdy caly release** (2,27 mld slow, zip 5,9 GB)
- Filtr: `status == "pri"` i tag `CLEANED_VERSION`
- Teksty pochodza z Shamela/JK — jakosc transkrypcji jest zmienna i mierzymy ja
  proxy jakosci OCR (T-011)

## 4. CAMeL Tools — kod

- Zasob: pakiet `camel-tools`, wersja zainstalowana **1.6.0**
- URL: <https://github.com/CAMeL-Lab/camel_tools>
- Licencja: **MIT** (klasyfikator PyPI `License :: OSI Approved :: MIT License`)
- Konsekwencja: brak ograniczen dla uzycia w projekcie

## 5. `calima-msa-r13` — baza morfologiczna

- Zasob: baza pobierana przez `camel_data`
- Licencja wg `09_DECISIONS.md` §7: **GPL-2**
- Konsekwencja: jesli kiedykolwiek redystrybuujesz pipeline **razem z baza**,
  calosc podlega GPL-2. Sam kod projektu redystrybuowany bez bazy tego nie wymaga
- Pochodzenie: oparta na publicznie dostepnej `almor-msa-r13` z MADAMIRA.
  **Nie wymaga licencji LDC** — to byl warunek wyboru (09_DECISIONS.md §1)

## 6. CAMeLBERT-CA — model jezykowy (E-14)

- Zasob: `CAMeL-Lab/bert-base-arabic-camelbert-ca` na HuggingFace
- Licencja: licencja modelu na HF
- Konsekwencja: **tylko wnioskowanie, bez fine-tuningu**
- Uwaga do raportu: model pretrenowany na danych typu OpenITI, ktore zawieraja
  cytaty koraniczne — kontaminacja prawdopodobna i musi byc adnotowana na kazdej
  figurze E-14

## 7. `chronologies.csv` — chronologia sur

- Zasob: `data/reference/chronologies.csv` (114 wierszy), dostarczony gotowy
- Zrodlo danych: tabela Tanzil, <https://tanzil.net/docs/revelation_order>
  (oparta na al-Zanjanim / Ibn 'Abbasie); atrybucja w kolumnie `source` pliku
- Licencja: dane z tanzil.net, atrybucja w pliku
- Weryfikacja programowa 2026-08-30 (`make verify-sources`): 114 wierszy,
  10 oczekiwanych kolumn, **86 mekkanskich, 28 medynskich, 35 wierszy
  z `exception_verses`** — zgodne z `09_DECISIONS.md` §2.4
- Uwaga: `order_sadeghi` **usuniete z designu** (Sadeghi, Arabica 58, i Blachere
  sa za paywallem). F9 pozostaje jako baseline literaturowy, ale definiowany
  operacyjnie — i tak ma byc opisane w raporcie

---

## 8. Zbiorczo: co wolno redystrybuowac

| Zasob | Redystrybucja tekstu w repo | Co commitujemy |
|---|---|---|
| EQTB | nie | parser, hashe, statystyki |
| QAC | **nie** (verbatim-only, bez modyfikacji) | tabela mapowania tagsetu, wynik ewaluacji |
| OpenITI | **nie** (CC-BY-NC-SA) | `ctrl_manifest.csv`, hashe, statystyki |
| `chronologies.csv` | tak, z atrybucja | plik zrodlowy |
| `calima-msa-r13` | nie (GPL-2 zaraza pipeline) | wersja bazy w configu |
