# 01 — Krytyczna recenzja planu v1

Skala severity:
- **BLOKER** — jeśli nie naprawisz, wynik główny jest nieinterpretowalny.
- **POWAŻNY** — wynik przetrwa, ale recenzent go rozbierze.
- **DO POPRAWY** — jakość/koszt/czytelność.

Ocena ogólna: plan jest bardzo dobrze zorganizowany inżyniersko (schemat danych,
ablacje, kontrola leakage) i słaby metodologicznie w warstwie **inferencji
przyczynowej o źródle różnic**. Ryzyko jest asymetryczne: pipeline dowiezie
liczby dla wszystkich 13 reprezentacji × 6 eksperymentów, a te liczby będą
mierzyć głównie gatunek, ortografię i błąd taggera, nie idiolekt.

---

## BLOKERY

### F-01. Test jednostronny bez hipotezy alternatywnej
`§31` lokalizuje `V_Quran` w rozkładzie korpusów jednoautorskich i raportuje
percentyl. To mówi tylko „jak nietypowo”, nie „w którą stronę”. Jeśli Koran
wypadnie na 95. percentylu — to nadal może być zwykły korpus jednoautorski
o nietypowym gatunku. Bez rozkładu alternatywnego (korpusy jawnie
wieloautorskie o tej samej wielkości i segmentacji) `RQ1` nie ma mocy
rozstrzygającej.
**Naprawa:** rozkład MIXTURE dla k = 2, 3, 5 autorów + raportowanie pozycji
Koranu względem **obu** rozkładów oraz ich strefy przekrycia. `02_DESIGN.md §3`.

### F-02. Asymetria anotacji: złoto vs. predykcja
`§3.1` i `§8`: Koran dostaje ręcznie zweryfikowaną morfologię QAC, OpenITI
dostaje wyjście CAMeL/Farasa. Bazy morfologiczne CAMeL to SAMA (MSA) i CALIMA
(EGY); dla Classical Arabic nie ma dedykowanej bazy, a disambiguator jest
trenowany na MSA. W efekcie **POS, morfologia i function words po stronie
OpenITI niosą systematyczny szum, którego Koran nie ma**. Każda różnica
„Koran vs. autorzy” w tych rodzinach cech jest wtedy nieodróżnialna od różnicy
„gold vs. predicted”.
**Naprawa (G1):** wszystkie cechy porównawcze liczone z **tego samego taggera
automatycznego po obu stronach**. QAC/EQTB służy wyłącznie do: (a) pomiaru
accuracy taggera na Quranic Arabic, (b) analiz *wewnątrz* Koranu. `03_DATA.md §5`.

### F-03. Konfund ortograficzny
Koran w wersji uthmani ma pisownię, której nie ma nigdzie indziej (ٱ waṣla,
alif chanjariyya, الصلوة, ﴾ symbole pauzy). Character n-gramy — twoja główna
„contamination-resistant” rodzina — rozdzielą Koran od OpenITI trywialnie, po
ortografii wydania, nie po stylu.
**Naprawa (G2):** używać warstwy **imlāʾī z EQTB** (EQTB dostarcza obie
ortografie), a na to nałożyć ten sam normalizator co na OpenITI. Obowiązkowy
**domain probe**: klasyfikator Koran-vs-OpenITI na samych cechach FUNCTIONAL;
jeśli AUC ≈ 1.0, transfer AV jest nieważny i trzeba to zaraportować, a nie ominąć.

### F-04. Konfund gatunku — najgroźniejszy i najsłabiej zaadresowany
Korpus kontrolny to proza: tafsīr, ḥadīth, ta'rīkh, fiqh, adab. Koran to tekst
rymowany, oralno-formularny, liturgiczny, z refrenami i formułami. `V_Quran`
porównywany do `V_within-author` liczonego na prozie porównuje **gatunki**, nie
autorów. Pseudo-book control z `§31` kontroluje wyłącznie *rozmiar* korpusu.
**Naprawa:** warstwa kontroli gatunkowej (`03_DATA.md §3`): maqāmāt (saʿ
al-Hamadhānī, al-Ḥarīrī), dywany poetyckie, zbiory duʿāʾ/chuṭab, oraz jawna
stratyfikacja `V` po gatunku z raportem, ile wariancji `V` wyjaśnia sam gatunek.

### F-05. Brak kontroli sanity dla AV poza domeną
`§29` zamraża model AV i stosuje go do Koranu. Nie ma kroku, który sprawdza,
co model robi z **znanym tekstem jednoautorskim spoza domeny treningowej**
(inny gatunek, inna epoka, inna ortografia). Jeśli model dla dywanu
al-Mutanabbiego też mówi „different-author”, to `P(same|Q_i,Q_j)` dla Koranu
nie niesie żadnej informacji o autorstwie.
**Naprawa:** E-07 w `05_EXPERIMENTS.md`. To jest eksperyment z prawem weta.

### F-06. Statystyka na obserwacjach zależnych
`§44`: Mann–Whitney U na rozkładach dystansów parowych. Dystanse parowe nie są
niezależne (każde okno wchodzi do wielu par). p-wartości będą zawyżone o rzędy
wielkości; Cliff's delta również. Bootstrap „na poziomie autorów i dzieł” jest
poprawny dla kontroli, ale dla Koranu brak analogicznego bloku.
**Naprawa (G5):** inferencja wyłącznie przez (a) statystyki zagregowane do
jednej liczby na autora/korpus (`V_A`) i (b) testy permutacyjne z blokowaniem
po `author_id` i po `surah_id`. Rozkłady parowe zostają jako opis, bez p.

### F-07. Okna przecinające granice sur i dzieł
`§9` tworzy okna stałej długości bez zastrzeżenia o granicach. Okno łączące
koniec sury mekkańskiej z początkiem medyńskiej ma etykietę okresu, która jest
fałszywa, i miesza rejestry.
**Naprawa (G3):** okna nigdy nie przekraczają `surah_id` (Koran) ani `book_id`
(OpenITI). Polityka dla sur krótszych niż okno — `03_DATA.md §6`.

---

## POWAŻNE

### F-08. Cyrkularność chronologii
Rekonstrukcje Nöldekego i pochodne opierają się m.in. na długości ajatów, typie
otwarcia sury i rymie — czyli na cechach stylometrycznych. Pytanie „czy da się
odtworzyć chronologię ze stylu” jest wtedy częściowo tautologiczne.
Sinai zauważa wprost, że typ elementu otwierającego surę koreluje ze średnią
długością ajatu. Plan v1 nie wspomina o tym ani razu.
**Naprawa:** (a) baseline „tylko średnia długość ajatu” dla każdego zadania
chronologicznego — model FUNCTIONAL musi go pobić, żeby cokolwiek znaczyć;
(b) rodzina cech prozodycznych oznaczona jako **jawnie cyrkularna** i
raportowana osobno; (c) analiza na resztach po wyregresowaniu długości ajatu.

### F-09. Chronologia traktowana jako pojedynczy fakt
`§10`: „wybrana rekonstrukcja”. Nöldeke–Schwally, wydanie kairskie, Blachère,
Bell i 7-fazowa chronologia Sadeghiego różnią się istotnie, a etykiety
Meccan/Medinan są przypisywane na poziomie sury, mimo że wiele sur jest
kompozytowych (interpolacje medyńskie w surach mekkańskich).
**Naprawa:** ≥ 3 uporządkowania jako analiza wrażliwości, `agreement matrix`
między nimi jako figura, oraz flaga `composite_sura` z listy klasycznych
raportów o interpolacjach; okna z tą flagą wykluczane w wariancie sensitivity.

### F-10. Brak pozycjonowania wobec literatury
Sadeghi, *The Chronology of the Qurʾān: A Stylometric Research Program*
(Arabica 58, 2011) robi dokładnie RQ2 metodami częstości morfemów i proponuje
„criterion of concurrent smoothness”; istnieje opublikowana krytyka tego
kryterium (*One Muhammad or Many Muhammads?*). Sayoud publikował dyskryminację
Koran/hadis. Plan v1 nie odnosi się do żadnej z tych prac.
**Naprawa:** markery Sadeghiego jako osobna rodzina cech-baseline (F9), a
„concurrent smoothness” jako testowana hipoteza, nie założenie.

### F-11. Powtarzalność wewnętrzna Koranu zawyża podobieństwo
Koran ma wysoką redundancję: formuły, refreny, powtarzane narracje. To
własność tekstu, nie idiolektu. Symetrycznie: kolekcje hadisów mają powtarzane
isnady, a tafsīr cytuje lemmata. Bez pomiaru i kontroli, `V` mierzy częściowo
stopień autoplagiatu, nie styl.
**Naprawa:** raport `internal near-duplicate rate` dla każdego korpusu +
wariant analizy po usunięciu near-duplicate n-gramów (MinHash, próg podany
w `03_DATA.md §7`).

### F-12. Brak kontroli mocy
30–50 autorów daje rozdzielczość percentyla ~2–3%. Nie da się wtedy uczciwie
napisać „p < 0.01” z rozkładu empirycznego 50 punktów.
**Naprawa:** minimum **60 autorów**, cel 100+; jawne raportowanie granicy
rozdzielczości i CI percentyla (bootstrap po autorach).

### F-13. `V` zależy od liczby okien i długości okna — brak matchingu
Wewnętrzna zmienność mierzona jako mediana dystansów parowych zależy od `n`
i od długości okna. Pseudo-book „o długości zbliżonej do Koranu” to za mało.
**Naprawa:** twarde dopasowanie: identyczna liczba okien, identyczna długość
okna, identyczny rozkład długości; B = 200 losowań podpróbki na korpus.

### F-14. Fitowanie wektoryzatorów i skalerów — nieopisana polityka
`§13`/`§24` nie mówią, na czym fitowany jest TF-IDF, `min_df`, `μ`, `σ` dla
Delty. Jeśli fitujesz na wszystkim łącznie z Koranem, masz leakage; jeśli na
Koranie — masz przewagę dla Koranu.
**Naprawa (G4):** słownik i statystyki fitowane **wyłącznie na CTRL-TRAIN**;
Koran i CTRL-TEST tylko transformowane. Zapisane jako artefakt z hashem.

### F-15. Składnia nieporównywalna między korpusami
OpenITI nie ma treebanku. QAC ma gold dla ~11k słów (ok. 40% pokrycia w wersji
oryginalnej); EQTB uzupełnia to parserem BiLSTM. Parsowanie OpenITI parserem
UD/CATiB trenowanym na MSA da jakość nieznaną i nieporównywalną.
**Naprawa:** cechy syntaktyczne **wyłącznie do analiz wewnątrz Koranu**
(Meccan/Medinan, change points). Wyjęte z AA/AV i z porównania `V`.

### F-16. Function words w arabskim zależą od segmentacji
Duża część słów funkcyjnych to proklityki (`wa-`, `fa-`, `bi-`, `li-`, `ka-`,
`al-`). Bez segmentacji morfologicznej nie da się ich policzyć, a wybór
segmentera (QAC vs. CAMeL vs. Farasa) zmienia częstości o dziesiątki procent.
Plan traktuje porównanie segmenterów jako ciekawostkę (`§8`), a jest to
zależność nośna dla F2 i F5.
**Naprawa:** jeden segmenter produkcyjny wybrany przed FREEZE na podstawie
accuracy wobec QAC; pozostałe wyłącznie jako analiza wrażliwości na jednej
rodzinie cech.

### F-17. Definicja „tokena” jest niejednoznaczna
`§3.1` mówi „ok. 77 tys. słów”; QAC to 77 430 słów ortograficznych, ale
~128 tys. segmentów morfologicznych, a EQTB raportuje ~132,7 tys. tokenów.
Okno „500 tokenów” znaczy więc trzy różne rzeczy.
**Naprawa:** jedna definicja w configu (`token_unit: orthographic_word`),
liczby weryfikowane programowo, nie przepisywane z dokumentacji.

### F-18. Wymiarowość vs. liczba jednostek
~193 okna Koranu wobec 50 000 cech TF-IDF. Dystanse w takiej przestrzeni są
zdominowane przez szum; Burrows's Delta klasycznie działa na 100–2000 MFW.
**Naprawa:** siatka MFW {100, 300, 1000, 3000} jako analiza wrażliwości;
figura „wynik vs. MFW” obowiązkowa — jeśli wniosek zmienia znak, nie ma wniosku.

### F-19. Brak floor'u szumu pomiaru
Nie wiadomo, ile wynosi `V` dla materiału, o którym *wiemy*, że jest
jednorodny (np. dwie połowy tej samej długiej sury). Bez tego nie da się
powiedzieć, czy `V_Quran` jest „duże”.
**Naprawa:** `V_within-surah` jako dolna kotwica skali.

### F-20. Brak testów negatywnych
Nie ma sprawdzenia, czy pipeline w ogóle *potrafi* wykryć wielogłosowość i czy
nie wykrywa jej tam, gdzie jej nie ma.
**Naprawa:** (a) MIXTURE (F-01), (b) test na przetasowanej chronologii — CPD
musi nie znajdować punktów, (c) symulacja szumu taggera: dołożenie do korpusu
kontrolnego błędu POS na poziomie zmierzonym w F-02 i sprawdzenie, jak
przesuwa `V`.

---

## DO POPRAWY

### F-21. Zakres nie jest „mini-projektem”
13 reprezentacji × 6 zadań + 4 transformery × 3 poolingi + 4 algorytmy CPD.
Tabela z `§49` to ~200 przebiegów eksperymentalnych plus tuning. To praca na
kwartały, nie na mini-projekt. Dodatkowo CAMeLBERT-CA był trenowany na danych
typu OpenITI, które zawierają cytaty koraniczne — kontaminacja jest bliska
pewności, więc koszt/korzyść tej gałęzi jest zły.
**Naprawa:** transformery → 1 model (CAMeLBERT-CA), 1 pooling (mean z 4
ostatnich warstw), status: eksploracja, osobny rozdział, brak wniosków
głównych. CPD → PELT + Kernel CPD.

### F-22. Brak warstwy inżynierskiej dla agenta
Brak: seedów, pinowania środowiska, kontraktów I/O między krokami, cache'owania
macierzy cech, testów jednostkowych na normalizację arabskiego, budżetu
obliczeniowego. Agent kodujący bez tego wyprodukuje nieodtwarzalne notebooki.
**Naprawa:** `08_REPO.md`.

---

## Werdykt

Plan v1 odpowiada na pytanie: *„jak bardzo Koran różni się wewnętrznie od
korpusów prozy klasycznej po przepuszczeniu przez asymetryczny pipeline
anotacji?”* — i na to pytanie odpowie precyzyjnie. Nie odpowiada na `RQ1`.

Wersja v2 zachowuje ~70% inżynierii v1 i wymienia warstwę projektu
eksperymentalnego. Największy pojedynczy zysk na jednostkę pracy: **F-02 + F-03
+ F-01**. Największe ryzyko projektowe: E-07 może pokazać, że AV poza domeną
nie działa — i wtedy `RQ4` trzeba porzucić. To jest akceptowalny wynik i musi
być zaplanowany jako możliwe zakończenie, a nie jako porażka.
