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

### Fallback T-010: referencja morfologiczna dla T-014 to EQTB, NIE QAC

`docs/09_DECISIONS.md` §2.2 przewiduje jawny fallback dla QAC (Quranic Arabic
Corpus, `corpus.quran.com`): strona pobierania wymaga podania adresu e-mail
w formularzu. Zgodnie z AGENTS.md zasada 9 ("bez rejestracji") i zasada
odtwarzalnosci T-051, **ten formularz nigdy nie zostanie uzyty** — to nie jest
tymczasowa przeszkoda czekajaca na reczne uzupelnienie, to sformalizowana
decyzja podjeta w T-010 (2026-08-30).

**Adnotacja obowiazkowa (09_DECISIONS.md §2.2):** referencja dla ewaluacji
taggera w T-014 to kolumny morfologiczne **EQTB** (`pos`, `pos_ar`, `features`,
`lemma`, `lemma_ar`, `root`, `root_ar`, ... — juz sparsowane w
`data/interim/eqtb_tokens.parquet`, T-009), **nie zewnetrzny plik QAC**. QAC
pozostaje uzyty wylacznie jako punkt odniesienia bibliograficzny/historyczny
(np. weryfikacja `n_tokens`, patrz sekcja powyzej) — nigdy jako zewnetrzne
dane wejsciowe do pipeline'u.

Odczyt maszynowy tej decyzji: `results/source_check.json` ->
`sources[id=qac].status == "fallback_active"` (nie `"degraded"` — status
`degraded` w tym repo oznacza problem czekajacy na naprawe, `fallback_active`
oznacza zaakceptowany, opisany stan koncowy). Implementacja rozroznienia:
`src/data/verify_sources.py::_apply_fallback`.

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

### Rozstrzygnieta rozbieznosc: `n_tokens` EQTB = 77429, nie "77430" (QAC)

`DEVIATIONS.md` D-06 (2026-08-30, pierwsza wersja) zanotowal roznice 1 slowa
miedzy `n_tokens` z EQTB (77429) a powszechnie cytowana liczba QAC "77430"
(Wikipedia, blogi typu riwaqalquran.com, equrancoaching.com) jako "known
negligible discrepancy" bez ustalonej przyczyny.

**Zrodlo pierwotne, nie wtorne** — `corpus.quran.com/java/example/tokencountexample.jsp`
(dokumentacja Java API samego QAC, pobrana 2026-08-30) publikuje dokladny
"Program Output" metody `Chapter.getTokenCount()` dla wszystkich 114 sur.
`Token` jest tam zdefiniowany jako "whitespace-delimited Arabic text within
a verse" — ta sama definicja co `token_unit: orthographic_word`
(`docs/09_DECISIONS.md` §6).

Porownanie programowe (`scripts/probe_word_count_discrepancy.py`,
artefakt: `results/eqtb_vs_qac_per_surah.csv`) tej tabeli z liczbami EQTB
distinct `(chapter_id, verse_id, word_id)` per sura:

- **0 z 114 sur roznych.** Zgodnosc chapter-po-chapter, bez wyjatku
  (sura 1 / Al-Fatiha = 29 w obu: 4+4+2+3+4+3+9 slow na werset 1–7;
  sura 114 = 20 w obu). Kandydat "konwencja liczenia basmali" odpada:
  roznica nie jest zlokalizowana w zadnej surze.
- Suma tabeli QAC Java API: **77429** — identyczna z EQTB, nie 77430.

**Wniosek:** rozbieznosc nie istnieje w naszych danych. Liczba "77430"
powtarzana w zrodlach trzeciorzednych jest niedokladnym/zaokraglonym cytatem —
nie zgadza sie z wlasnym, autorytatywnym wyjsciem modelu danych QAC. `n_tokens`
EQTB = 77429 jest wiec **dokladnym**, a nie tylko "w tolerancji", odpowiednikiem
referencji QAC. `DEVIATIONS.md` D-06 zaktualizowany o ten wynik.

---

## 5. T-014: kubelek ADV (gold T/LOC) — N i diagnostyka bledu

Ewaluacja: `results/tagger_eval.json` (`per_pos_coarse`), n=77429 slow
ortograficznych, CAMeL MLE + calima-msa-r13 vs EQTB gold. Mapowanie:
`data/reference/eqtb_camel_pos_map.csv` (`adv` → EQTB `T`, coarse ADV;
CAMeL nie rozdziela T vs LOC).

### N per kubelek coarse (nie udział)

| kubelek | N (gold) | correct | accuracy |
|---------|----------|---------|----------|
| NOUN    | 29046    | 24630   | 0.848    |
| VERB    | 19356    | 16256   | 0.840    |
| PART    | 8439     | 2984    | 0.354    |
| PREP    | 7678     | 7517    | 0.979    |
| PRON    | 7675     | 4874    | 0.635    |
| ADJ     | 1952     | 470     | 0.241    |
| ADV     | 1843     | 13      | 0.007    |
| CONJ    | 1440     | 1007    | 0.699    |

ADV = **1843** (T=1171, LOC=672; `results/tagger_adv_diagnosis.json`),
czyli 2,4% korpusu — **nie** kategoria z 20 wystąpieniami. 13 trafien
(acc 0.007) przy N tej wielkości wymaga diagnozy, nie odrzucenia jako szum.

Fine POS / partykuły (PART N=8439, acc 0.354) to osobny, juz opisany
rozjazd ziarnistosci: EQTB ma 20+ tagow partykul (`ACC`…`VOC`), CALIMA
sklada je do `part_*` / ogolnego `part` (`eqtb_camel_pos_map.csv`,
`mapped=false` dla gołego `part`). ADV **nie** wpisuje sie w ten sam
wzorzec: CAMeL **ma** tag `adv` (13 wystapien `adv` na gold ADV; 2
`adv_interrog` schodza do PART po mapie, nie do ADV).

### Co CAMeL przewiduje na 1843 gold ADV

Z `results/tagger_adv_diagnosis.json` → `pred_coarse_on_gold_adv`
(ponowne otagowanie 1457 wersetow z co najmniej jednym T/LOC, alignment
powierzchni jak w T-014):

- NOUN 832 (0.45) — raw: `noun` 734, `noun_prop` 98
- CONJ 774 (0.42) — raw: `conj` 774
- PREP 136 (0.07)
- VERB 43, PRON 27, ADJ 16, ADV 13, PART 2

Dwie rodziny pokrywaja 87% przypadkow. To nie jest rozproszony blad taggera.

### Konkretne lokalizacje (seed `t014_adv_errors`, n=12)

Rodzina CONJ — EQTB T (okolicznik czasu), CAMeL `conj`:

- `26:80:1` surface `واذا`, gold T / lemma `اذا`, pred CONJ/`conj`
- `29:16:2` surface `اذ`, gold T / lemma `اذ`, pred CONJ/`conj`
- `46:29:9` surface `فلما`, gold T / lemma `لما`, pred CONJ/`conj`
- `62:9:4` surface `اذا`, gold T / lemma `اذا`, pred CONJ/`conj`

Rodzina NOUN — EQTB T/LOC, CAMeL `noun` / `noun_prop`:

- `20:64:8` surface `اليوم`, gold T / lemma `يوم`, pred NOUN/`noun`
- `3:167:20` i `75:13:3` surface `يوميذ`, gold T / lemma `يوميذ`,
  pred NOUN/`noun_prop` (własna nazwa)
- `8:55:4` surface `عند`, gold LOC / lemma `عند`, pred NOUN/`noun`
- `58:13:4` surface `بين`, gold LOC / lemma `بين`, pred NOUN/`noun`

Rodzina PREP — EQTB LOC, CAMeL `prep` (schemat, nie pomyłka powierzchni):

- `25:27:9` i `28:88:3` surface `مع`, gold LOC / lemma `مع`, pred PREP/`prep`

Pozostaly szum taggera (nie schemat): `7:134:20` surface `معك`, gold LOC
/ lemma `مع`, pred VERB/`verb` (zla analiza morfemowa مع+ك).

### Wniosek

N(ADV) jest duze. Acc 0.007 **nie** oznacza, ze tagger „nie umie przyslowkow"
w sensie braku kategorii: `adv` istnieje i mapuje sie 1:1 na EQTB `T`
(`eqtb_camel_pos_map.csv` wiersz `adv,T,ADV,true`). Klasa zamknieta
koranicznych T/LOC (`إذ`/`إذا`/`لما`, `يوم`/`يومئذ`, `عند`/`بين`/`مع`)
siedzi w CAMeL MSA w `conj` / `noun` / `prep` — to **ziarnistosc i schemat
tagsetu** (QAC/EQTB vs CALIMA), analogiczna w duchu do 20+ partykul, tylko
na innej osi (T vs CONJ, LOC vs N/P), nie do naprawienia zmiana
disambiguatora MLE→BERT. BERT moze zmienic ogon VERB/noun_prop
(`معك`, `يوميذ`); nie zmieni konwencji `إذا`=conj.

Accuracy coarse 0.746 z T-014 zostaje; kubelek ADV nie jest uzywany jako
osobna cecha przed FREEZE. Raportowac jako ograniczenie tagsetu, nie jako
porazke taggera na rzadkiej klasie.

