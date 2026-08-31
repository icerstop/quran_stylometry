# Makefile — quran-stylometry
#
# Kolejnosc targetow wg docs/08_REPO.md §6.
# Blokada zadan klastrowych wg docs/11_HANDOFF.md §6.
#
# Konwencja recipe: kazda linia to JEDNO wywolanie `python -m src.cli ...`.
# Bez `source`, bez `&&`, bez builtinow powloki — recipe musza dzialac zarowno
# pod /bin/sh, jak i pod cmd.exe (GNU Make na Windowsie).

PY      ?= python
CONFIG  ?= configs/base.yaml

# HOST_ROLE ustawiane w configs/env.local.yaml (poza gitem). Agent nie ma jak
# przelaczyc sie na `cluster`, bo nie ma dostepu do klastra.
HOST_ROLE ?= laptop

CLUSTER_TASKS := tag-ctrl variance-array av-train embed

.PHONY: help setup setup-nlp verify-sources test lint format \
        data download-eqtb formalize-qac-fallback select-ctrl normalize cap-ctrl tag clean-quotes dedup chronology segment splits features gates freeze main \
        chrono explore figs figs-smoke dashboard audit sample-run \
        handoff handoff-verify $(CLUSTER_TASKS)

help:
	@$(PY) -m src.cli --help

# --- P0: srodowisko -----------------------------------------------------
setup:
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"
	$(PY) -m src.cli init-env
	@echo Gotowe. Tagger (T-014+) instalujesz osobno: make setup-nlp

# camel_data -i light to 19 MB (10_COMPUTE.md §5); `full` tylko na klastrze,
# do $SCRATCH. Osobny target, bo camel-tools ma zaleznosc kompilowana i nie
# moze blokowac `make setup` na czystym srodowisku.
setup-nlp:
	$(PY) -m pip install -e ".[nlp]"
	camel_data -i light

verify-sources:
	$(PY) -m src.cli verify-sources --config $(CONFIG) --out results/source_check.json

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check src tests
	$(PY) -m black --check src tests
	$(PY) -m mypy

format:
	$(PY) -m black src tests
	$(PY) -m ruff check --fix src tests

# --- P1..P6: etapy pipeline'u -------------------------------------------
data:
	$(PY) -m src.cli data --config $(CONFIG)

# T-009 samodzielnie (nie czeka na T-010..T-012). Wymaga 7-Zip — patrz
# pyproject.toml (zaleznosci systemowe) i docs/09_DECISIONS.md §2.1.
download-eqtb:
	$(PY) -m src.cli download-eqtb --config $(CONFIG)

# T-010: NIE pobiera QAC (formularz e-mail koliduje z AGENTS.md / T-051).
# Formalizuje fallback z 09_DECISIONS.md §2.2 — referencja to EQTB.
formalize-qac-fallback:
	$(PY) -m src.cli formalize-qac-fallback --config $(CONFIG)

# T-011: metadane juz w data/raw/openiti/; pelny algorytm §3 (siec: jakosc + teksty).
select-ctrl:
	$(PY) -m src.cli select-ctrl --config $(CONFIG)

normalize:
	$(PY) -m src.cli normalize --config $(CONFIG)

cap-ctrl:
	$(PY) -m src.cli cap-ctrl --config $(CONFIG)

tag:
	$(PY) -m src.cli tag --config $(CONFIG)

clean-quotes:
	$(PY) -m src.cli clean-quotes --config $(CONFIG)

dedup:
	$(PY) -m src.cli dedup --config $(CONFIG)

chronology:
	$(PY) -m src.cli chronology --config $(CONFIG)

segment:
	$(PY) -m src.cli segment --config $(CONFIG)
	$(PY) -m src.cli splits --config $(CONFIG)

splits:
	$(PY) -m src.cli splits --config $(CONFIG)

features:
	$(PY) -m src.cli features --config $(CONFIG)

gates:
	$(PY) -m src.cli gates --config $(CONFIG)

# `make freeze` musi zawiesc, jesli `make gates` nie zostal uruchomiony
# na aktualnym configu (08_REPO.md §6). Warunek sprawdza CLI, nie Makefile,
# zeby byl przenosny i testowalny.
freeze:
	$(PY) -m src.cli freeze --config $(CONFIG)

# `make main` musi zawiesc bez configs/frozen/ (AGENTS.md zasada 2).
main:
	$(PY) -m src.cli main --config $(CONFIG)

chrono:
	$(PY) -m src.cli chrono --config $(CONFIG)

explore:
	$(PY) -m src.cli explore --config $(CONFIG)

figs:
	$(PY) -m src.cli figs --config $(CONFIG)

figs-smoke:
	$(PY) -m src.cli figs-smoke --config $(CONFIG)

dashboard:
	$(PY) -m src.cli dashboard --config $(CONFIG)

audit:
	$(PY) -m src.cli audit --config $(CONFIG)

sample-run:
	$(PY) -m src.cli sample-run --config $(CONFIG)

# --- Zadania klastrowe: zablokowane lokalnie (11_HANDOFF.md §6) ----------
$(CLUSTER_TASKS):
ifneq ($(HOST_ROLE),cluster)
	@echo BLOCKED: '$@' to zadanie klastrowe.
	@echo Agent: uruchom 'make handoff JOB=H1' (albo H2 / H3) i zatrzymaj sie.
	@exit 1
endif
	$(PY) -m src.cli $@ --config $(CONFIG)

handoff:
	$(PY) -m src.cli build-handoff --job $(JOB) --out handoff/$(JOB)

handoff-verify:
	$(PY) -m src.cli verify-handoff --job $(JOB) --strict
