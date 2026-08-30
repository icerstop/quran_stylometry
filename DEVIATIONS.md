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

### D-04 · Format EQTB — otwarty blocker, nie odstepstwo

`corpus/Quran.csv` w repozytorium `NoorBayan/Quranic` jest tabela na poziomie
ajatu (UTF-16-LE, TAB, 5 kolumn), a nie tabela tokenowa o ~43 kolumnach opisana
w `09_DECISIONS.md` §2.1. Zgloszone jako blocker w `results/blockers.jsonl`;
nie zgadywano mapowania. Rozstrzygniecie nalezy do T-009.
