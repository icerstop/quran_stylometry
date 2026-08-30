"""Dopisuje wpisy T-001..T-008 do `results/runs.jsonl` (AGENTS.md, format postepu).

Uruchamiany raz, po commicie P0 — dzieki temu kazdy wpis niesie `git_sha`
commita, ktory zawiera opisywany kod, a nie `null`.

    python scripts/log_p0_runs.py
"""

from __future__ import annotations

from typing import Any

from src.config import load_config
from src.paths import CONFIGS_DIR, RUNS_LOG_PATH
from src.utils.runs import log_run

P0_RUNS: list[dict[str, Any]] = [
    {
        "task": "T-001",
        "artifacts": ["pyproject.toml", "Makefile", ".pre-commit-config.yaml", ".gitignore"],
        "metrics": {"n_makefile_targets": 24, "n_pinned_core_deps": 11},
        "note": (
            "GNU Make 4.4.1 (ezwinports) + git init. Kazdy recipe to jedno wywolanie "
            "python -m src.cli, bez source i &&, zeby dzialalo pod cmd.exe. "
            "camel-tools 1.6.0 instaluje sie na Windowsie bez kompilatora, ale ciagnie "
            "torch — dlatego zostaje w ekstrze [nlp] i osobnym targecie setup-nlp."
        ),
    },
    {
        "task": "T-002",
        "artifacts": [
            "configs/base.yaml",
            "configs/laptop_only.yaml",
            "configs/normalizer.yaml",
            "src/config.py",
            "src/cli.py",
        ],
        "metrics": {"n_feature_configs": 9, "n_experiment_configs": 14},
        "note": (
            "config_hash = sha256 kanonicznego JSON-a zwalidowanego modelu, nie bajtow "
            "pliku: formatowanie YAML i kolejnosc kluczy nie zmieniaja hasha. "
            "env.local.yaml (HOST_ROLE) jest z hasha wykluczony."
        ),
    },
    {
        "task": "T-003",
        "artifacts": ["DATA_LICENSES.md", "SOURCES.md", "DEVIATIONS.md"],
        "metrics": {"n_sources_documented": 7},
        "note": (
            "Licencje odczytane przez API: EQTB MIT (GitHub), QAC GPL (strona), "
            "OpenITI cc-by-nc-sa-4.0 (Zenodo). Ostatnia jest wezsza niz 'open access' "
            "z 09_DECISIONS §7 — zapisano zmierzona wartosc, docs nietkniete, "
            "roznica zgloszona w DEVIATIONS.md D-01."
        ),
    },
    {
        "task": "T-004",
        "artifacts": ["src/utils/seed.py", "tests/test_determinism.py"],
        "metrics": {"n_tests": 5},
        "note": (
            "PYTHONHASHSEED da sie tylko zweryfikowac, nie naprawic w runtime, wiec "
            "SeedReport raportuje stan zamiast go udawac. Osobny strumien RNG na etap: "
            "dolozenie etapu nie przesuwa losowan w etapach juz policzonych."
        ),
    },
    {
        "task": "T-005",
        "artifacts": [
            "src/utils/logging.py",
            "src/utils/hashing.py",
            "src/utils/runs.py",
            "src/utils/provenance.py",
        ],
        "metrics": {"n_tests": 9},
        "note": (
            "status='blocked' bez wpisu w blockers.jsonl podnosi MissingBlockerError. "
            "git_sha zawsze z git rev-parse; brak repo daje jawne null + git_state, "
            "nigdy zmyslonej wartosci."
        ),
    },
    {
        "task": "T-006",
        "artifacts": ["src/utils/cache.py", "tests/test_cache.py"],
        "metrics": {"n_tests": 12},
        "note": (
            "Nazwa katalogu niesie odcisk CALEGO klucza, nie sam config_hash — inaczej "
            "dwa rozne klucze wskazywalyby ten sam katalog i niezgodnosc wychodzilaby "
            "dopiero jako blad integralnosci przy odczycie."
        ),
    },
    {
        "task": "T-007",
        "artifacts": ["src/schemas.py", "src/utils/io.py", "tests/test_schema.py"],
        "metrics": {"n_tests": 27},
        "note": (
            "GuardrailViolationError NIE dziedziczy po ValueError: pydantic zamienilby "
            "go na ValidationError i zlamanie G1 wygladaloby jak literowka w danych. "
            "Chronology ma pola z 09_DECISIONS §2.4 (order_canonical/traditional/"
            "noldeke), nie z 03_DATA §9 — hierarchia dokumentow, patrz DEVIATIONS D-02."
        ),
    },
    {
        "task": "T-008",
        "artifacts": [
            "src/viz/style.py",
            "src/viz/save.py",
            "src/viz/fig00_smoke.py",
            "figures/INDEX.md",
        ],
        "metrics": {"n_tests": 17},
        "note": (
            "G9 egzekwowany w FigureSpec.__post_init__: figura typu 'result' bez "
            "kotwicy kontrolnej nie powstaje. INDEX.md jest upsertowany po markerze "
            "fig_id, wiec regeneracja jednej figury nie rusza pozostalych wpisow."
        ),
    },
]


def main() -> int:
    config = load_config(CONFIGS_DIR / "base.yaml")
    config_hash = config.config_hash()
    for entry in P0_RUNS:
        record = log_run(
            task=entry["task"],
            status="done",
            config_hash=config_hash,
            artifacts=entry["artifacts"],
            metrics=entry["metrics"],
            note=entry["note"],
        )
        print(f"{record.task}: {record.status} (git_sha={record.git_sha})")
    print(f"\nZapisano {len(P0_RUNS)} wpisow do {RUNS_LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
