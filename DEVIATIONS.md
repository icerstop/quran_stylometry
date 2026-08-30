# DEVIATIONS.md — odstepstwa od preregistracji

Kazda zmiana hiperparametru albo procedury **po FREEZE (T-033)** wymaga wpisu
tutaj: co zmieniono, dlaczego, i jak wynik wyglada w obu wariantach
(AGENTS.md zasada 7).

Format wpisu:

```
## YYYY-MM-DD — <co>
- Parametr / procedura:
- Bylo -> jest:
- Powod:
- Wynik przed zmiana:
- Wynik po zmianie:
- config_hash przed / po:
```

---

## Stan na 2026-08-30

**Brak odstepstw — FREEZE (T-033) jeszcze nie nastapil.** Do tego momentu
parametry zmienia sie normalnie w `configs/`, bez wpisu tutaj.

Ponizej rzeczy, ktore **nie sa** odstepstwami od preregistracji, ale zostaly
ustalone empirycznie w P0 i moga wygladac na rozbieznosc wobec dokumentacji.
Zapisane, zeby nie trzeba bylo ich odkrywac drugi raz.

### D-01 · Licencja OpenITI: `cc-by-nc-sa-4.0`, nie "open access"

`docs/09_DECISIONS.md` §7 opisuje OpenITI jako "open access". Zenodo API dla
concept DOI `10.5281/zenodo.3082463` zwraca `metadata.license.id =
"cc-by-nc-sa-4.0"` (wersja 2025.1.9, rekord 17767721). Klauzula **NC** moze
dotyczyc sposobu publikacji. Zapisano zmierzona wartosc w `DATA_LICENSES.md`;
`docs/` nie modyfikowano. Do decyzji czlowieka przed publikacja.

### D-02 · `03_DATA.md` §9 vs `09_DECISIONS.md` §2.4 — nazwy pol chronologii

`03_DATA.md` §9 wymienia `order_cairo` i `order_sadeghi`. `09_DECISIONS.md` §2.4
definiuje `order_canonical / order_traditional / order_noldeke` i usuwa
`order_sadeghi` (Arabica 58 za paywallem). Naglowek `03_DATA.md` mowi wprost, ze
przy rozbieznosci wygrywa `09_DECISIONS.md` — `src/schemas.py::Chronology` ma
wiec trzy pola z §2.4. To nie jest odstepstwo, tylko rozstrzygniecie hierarchii
dokumentow.

### D-03 · `camel-tools` na Windowsie: ryzyko nie zmaterializowalo sie

Plan P0 zakladal, ze `camel-tools` moze nie zainstalowac sie bez kompilatora C++
(zaleznosc `camel-kenlm`). Wersja **1.6.0** instaluje sie na Windowsie z gotowych
kol; ciagnie natomiast `torch` i `transformers`. Dlatego ekstra `[nlp]` zostaje
osobno — ale z powodu **wagi drzewa zaleznosci**, nie z powodu kompilacji.
Wybor taggera bez zmian.

### D-04 · Format EQTB — rozstrzygniete 2026-08-30, nie odstepstwo

`corpus/Quran.csv` w repozytorium `NoorBayan/Quranic` jest tabela na poziomie
ajatu (UTF-16-LE, TAB, 5 kolumn), a nie tabela tokenowa o ~43 kolumnach opisana
w `09_DECISIONS.md` §2.1. Zgloszone jako blocker w `results/blockers.jsonl`
(nie zgadywano mapowania) — **rozstrzygniete, patrz D-05.** Oba wpisy blockera
sa domkniete (`resolved: true`) w `results/blockers.jsonl`, nie usuniete.

### D-05 · Mapowanie kolumn EQTB — jedno potwierdzone, jedno swiadomie otwarte

Tabela tokenowa lezy w `corpus/Quranic.rar` -> `Quranic.csv` (UTF-16-LE, TAB,
51 kolumn), nie plasko w `corpus/`. 40 z 42 kolumn z `09_DECISIONS.md` §2.1
wystepuje werbatim. Rozstrzygniecie z `09_DECISIONS.md` §2.1 (2026-08-30):

- `constituent_position` <- `constituents_loc` — **potwierdzone**, mapowane
  1:1 w `src/data/download_eqtb.py`.
- `constituent_node` — **swiadomie nierozstrzygniete.** Zostaje
  nullable/`unmapped` w `Window`, bo `docs/04_FEATURES.md` §F7 nie uzywa pol
  `constituent_*`. Szczegoly i dowody: `SOURCES.md` §4.

`make verify-sources` sprawdza teraz wylacznie osiagalnosc `corpus/Quranic.rar`
(maly ranged GET, bez 7-Zip, bez ekstrakcji) — pelne rozpakowanie i parsowanie
to praca `T-009` (`src/data/download_eqtb.py`), wykonana raz, z wynikiem
cache'owanym w `data/raw/eqtb/` i `data/interim/eqtb_tokens.parquet`. 7-Zip
jest udokumentowany jako zaleznosc systemowa w `pyproject.toml`.

T-009 wykonany 2026-08-30: `n_surahs=114` (zweryfikowane programowo, zgodne
z `09_DECISIONS.md` §2.4), `n_verses=6236` — patrz `results/corpus_stats.json`.
Pierwotna wartosc `n_tokens=128219` z tego samego przebiegu bylo bledna —
patrz D-06.

### D-06 · `n_tokens` EQTB pomylone z `n_segments` — poprawione tego samego dnia

Pierwsza wersja `compute_corpus_stats` (T-009, 2026-08-30) liczyla `n_tokens`
jako liczbe wierszy `Quranic.csv` po odfiltrowaniu placeholderow (128219).
To jest `token_unit: orthographic_word` z `docs/09_DECISIONS.md` §6? **Nie.**
128219 to liczba **segmentow morfologicznych** (kazdy wiersz = jeden segment:
proklityka, temat, sufiks moga byc osobnymi wierszami dla jednego slowa).

Sprawdzone programowo na calym `data/interim/eqtb_tokens.parquet`:
- `distinct (chapter_id, verse_id, word_id)` po odfiltrowaniu placeholderow
  = **77429**, w porownaniu z referencyjna liczba QAC **77430** (roznica: 1,
  nie zbadana dalej — brak dowodu na konkretna przyczyne, nie zgadywano;
  zadna weryfikacja nie wykazala duplikatow/dziur w `word_id` w zadnym
  wersecie: `distinct(word_id) == max(word_id)` dla wszystkich 6236 wersetow).
- Samo `(verse_id, word_id)` **bez** `chapter_id` dawalo tylko 9898 — `verse_id`
  resetuje sie co sure (max obserwowana wartosc: 286, liczba wersetow
  Al-Baqary), wiec wersety z roznych sur zderzaly sie na tym samym numerze.

Identyfikacja wiersza-placeholdera zweryfikowana empirycznie, nie zgadywana:
`word_id == '0'` jest identyczny zbior co `location == '_'` (11157 z 11157
wierszy w obu, XOR = 0, na calym pliku). To NIE jest `rel_label == 'root'` —
`rel_label` tych wierszy przyjmuje 75 roznych wartosci (`Subj` 6104x, `Pred`
1444x, `Adj` 758x, `root` tylko 520x, ...), bo koduje relacje CALEJ klauzuli
do nadrzednej struktury (wirtualny wezel per klauzula), nie fakt bycia korzeniem.

Poprawka: `compute_corpus_stats` teraz zwraca `n_tokens` (distinct slowa) i
`n_segments` (wiersze) jako dwa osobne pola. Regresja zablokowana testami w
`tests/test_eqtb_token_count.py` (syntetyczne slowo 3-segmentowe + tolerancja
±1% wobec referencji QAC na prawdziwym pliku, jesli istnieje lokalnie).
`results/corpus_stats.json` przeliczony: `n_tokens=77429`, `n_segments=128219`.
