# 11 — Protokół przekazania laptop ↔ klaster

Zasada nadrzędna: **agent nie ma dostępu do klastra.** Nie zna hosta, nie ma
kluczy SSH, nie uruchamia `sbatch`, `srun`, `scp` ani `rsync`. Jedyne, co robi,
to przygotowanie paczki zadania i zatrzymanie się. Ty przeglądasz i wysyłasz.

To nie jest tylko kwestia bezpieczeństwa. Agent nie widzi kolejki, limitów
grantu ani quoty — więc nawet działając w dobrej wierze potrafi wysłać dziesięć
jobów po 10 h, bo „chciał mieć wyniki szybciej".

---

## 1. Ile razy w ogóle siadasz do klastra

Trzy razy. Zadania zostały pogrupowane tak, żeby nie było więcej.

| Handoff | Kiedy | Zawartość | Zasób | Czas |
|---|---|---|---|---|
| **H1** | przed FREEZE | T-015 tagowanie CTRL + tagowanie kotwic z T-041 | 1× GPU | 4–8 h |
| **H2** | po FREEZE | T-035 wariancja (array 0-3) + T-038/T-039 AV z bramką OOD | CPU, 64 GB | 4–6 h |
| **H3** | opcjonalny | T-048 embeddingi CAMeLBERT-CA | 1× GPU | 1–2 h |

**T-032 (siatka MFW × okno) przeniesione na laptop** wbrew `10_COMPUTE.md` —
to dwanaście przebiegów AA, które spokojnie przechodzą przez noc lokalnie.
Jeden handoff mniej jest wart więcej niż te trzy godziny.

H2 celowo łączy wariancję i AV w jedno wejście: model AV i bramka OOD muszą
działać na tym samym zamrożonym artefakcie, więc rozbicie ich na dwa handoffy
tworzy okazję do pomyłki.

---

## 2. Struktura paczki

Agent tworzy `handoff/<H1|H2|H3>/` i nic poza tym katalogiem nie rusza:

```text
handoff/H1/
├── README.md                # co robi, ile trwa, co ma wrócić
├── job.sbatch               # skrypt SLURM, bez sekretów, z twardymi limitami
├── config.frozen.yaml       # dokładny config + jego sha256 w nagłówku
├── inputs.manifest.json     # pliki do wysłania: ścieżka, rozmiar, sha256
├── expected_outputs.json    # co ma wrócić: ścieżka, schemat, walidacja
└── dryrun.sbatch            # ten sam job z --limit-files 50, --time 00:20:00
```

`inputs.manifest.json` istnieje po to, żebyś nie zgadywał, co rsyncować, i żeby
po powrocie dało się sprawdzić, że job liczył to, co myślisz.

---

## 3. Twoja checklista przed `sbatch`

Sześć punktów, minuta roboty:

1. `job.sbatch` ma **jawne** `--time`, `--mem`, `--gres`, `--cpus-per-task`.
   Brak któregokolwiek → odsyłasz paczkę.
2. Nie ma `--exclusive`, nie ma `--array` szerszego niż zapowiedziany w README,
   nie ma pętli `for ... sbatch`.
3. Wszystkie ścieżki wyjściowe wskazują na `$SCRATCH`, żadna na `$HOME`.
4. `CAMELTOOLS_DATA`, `HF_HOME`, `TRANSFORMERS_CACHE` ustawione na `$SCRATCH`.
5. Job ma checkpointing (`--checkpoint-every`) — inaczej padnięcie w 7. godzinie
   kosztuje cały dzień.
6. **Najpierw `dryrun.sbatch`.** Dopiero gdy przejdzie, pełny job.

Punkt 6 nie jest formalnością. Pierwsze uruchomienie taggera na tekstach OpenITI
prawie na pewno wywali się na jakimś znaku, którego normalizator nie przewidział.
Lepiej dowiedzieć się tego po dwudziestu minutach niż po sześciu godzinach.

---

## 4. Co agent robi w międzyczasie

Kluczowe: agent **nie czeka bezczynnie**. Wpisuje do `results/runs.jsonl` status
`awaiting_cluster` i przechodzi na niezależną gałąź DAG-u.

Podczas H1 (czeka na tagi) może robić:
`T-016` detekcja cytatów, `T-017` redundancja, `T-018` chronologia,
`T-019` segmentacja, `T-020` splity, `T-021` character n-grams,
`T-026` structural, `T-028` prozodia, `T-034` korpusy syntetyczne,
`T-008` cały szkielet `src/viz/` i figury A z EDA.

Zablokowane do powrotu H1: `T-022` (function words), `T-023` (lemmas/roots),
`T-024` (POS), `T-025` (morfologia) — wszystko, co potrzebuje tagów.

Podczas H2 może domykać figury, dashboard i `T-043`…`T-047` na tych rodzinach
cech, które już ma.

---

## 5. Powrót — walidacja, nie zaufanie

Po `rsync` z klastra uruchamiasz na laptopie:

```bash
make handoff-verify JOB=H1
```

Sprawdza cztery rzeczy i kończy niezerowym kodem przy każdej rozbieżności:

1. wszystkie pliki z `expected_outputs.json` istnieją i mają niepustą treść,
2. `config_hash` w metadanych wyników **zgadza się** z `config.frozen.yaml`,
3. schematy się walidują (kolumny, typy, brak NaN w polach obowiązkowych),
4. pokrycie: liczba otagowanych tokenów zgadza się z `inputs.manifest.json`
   — jeśli job przetworzył 2,8 mln zamiast 3,1 mln tokenów, znaczy że coś
   po cichu odpadło i trzeba znaleźć co.

Punkt 4 wyłapuje najczęstszy cichy błąd w tym pipelinie: pliki, które tagger
pominął przy wznowieniu z checkpointu.

Dopiero po zielonym `handoff-verify` agent dostaje zgodę na `T-022`…`T-025`.

---

## 6. Egzekwowanie po stronie kodu

`Makefile` blokuje uruchomienie zadań klastrowych lokalnie:

```makefile
HOST_ROLE ?= laptop

CLUSTER_TASKS := tag-ctrl variance-array av-train embed

$(CLUSTER_TASKS):
ifneq ($(HOST_ROLE),cluster)
	@echo "BLOCKED: '$@' to zadanie klastrowe."
	@echo "Agent: uruchom 'make handoff JOB=<H1|H2|H3>' i zatrzymaj sie."
	@exit 1
endif
	python -m src.cli $@ --config $(CONFIG)

handoff:
	python -m src.cli build-handoff --job $(JOB) --out handoff/$(JOB)

handoff-verify:
	python -m src.cli verify-handoff --job $(JOB) --strict
```

`HOST_ROLE` ustawiane w `configs/env.local.yaml`, którego **nie ma w repo**
(jest w `.gitignore`) i który agent tworzy z wartością `laptop`. Na klastrze
ustawiasz go ręcznie w `.bashrc`. Agent nie ma jak przełączyć się na `cluster`,
bo nie ma tam dostępu.

Dodatkowo w `AGENTS.md` zasada twarda nr 10:

> Nie uruchamiasz `sbatch`, `srun`, `ssh`, `scp` ani `rsync`. Nie szukasz
> kluczy SSH ani adresów hostów. Zadania klastrowe kończysz przez
> `make handoff JOB=<id>` i wpis `awaiting_cluster`.

---

## 7. Gdy job padnie

Agent nie diagnozuje klastra — nie widzi logów, dopóki mu ich nie dasz.
Procedura: wklejasz mu ogon `logs/tag_ctrl_<jobid>.out`, agent proponuje
poprawkę w `src/` i **nową paczkę** `handoff/H1b/`, z adnotacją, co się
zmieniło względem H1. Nigdy nie modyfikuje paczki, która już poszła — historia
handoffów ma zostać czytelna, bo to jedyny ślad po tym, co faktycznie policzył
klaster.
