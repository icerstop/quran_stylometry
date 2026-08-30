"""Punkt wejscia CLI. Cala warstwa stanu zyje tutaj; `src/` ponizej jest czysty.

Kazdy target z Makefile'a woła dokladnie jedna podkomende tego modulu — dzieki
temu recipe sa przenosne miedzy /bin/sh a cmd.exe.

Etapy jeszcze niezaimplementowane (P1..P6) NIE sa cichymi no-opami: koncza sie
kodem 2 i komunikatem wskazujacym zadanie z docs/07_TASKS.md. Cichy sukces
pustego etapu jest gorszy niz jawna porazka.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from src.config import Config, load_config
from src.paths import (
    CONFIGS_DIR,
    ENV_LOCAL_PATH,
    FROZEN_CONFIG_DIR,
    RESULTS_DIR,
    SOURCE_CHECK_PATH,
    rel_to_repo,
)
from src.utils.io import ensure_dir, write_json, write_yaml
from src.utils.logging import get_logger

LOGGER = get_logger("src.cli")

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_NOT_IMPLEMENTED = 2
EXIT_BLOCKED = 3

DEFAULT_CONFIG = CONFIGS_DIR / "base.yaml"
DEFAULT_SOURCES = CONFIGS_DIR / "sources.yaml"

# Etapy pipeline'u, ktore nalezą do pozniejszych faz. Mapowanie na zadania
# z docs/07_TASKS.md, zeby komunikat mowil, co dokladnie trzeba zrobic.
PENDING_STAGES: dict[str, str] = {
    "data": "T-009..T-012 (P1)",
    "normalize": "T-013 (P2)",
    "tag": "T-014, T-015 (P2)",
    "clean-quotes": "T-016, T-017 (P1)",
    "segment": "T-019, T-020 (P2)",
    "features": "T-021..T-028 (P2)",
    "gates": "T-029..T-032 (P3)",
    "chrono": "T-043..T-047 (P6)",
    "explore": "T-048 (P6)",
    "figs": "T-035..T-047 (figury z results/)",
    "dashboard": "T-049 (P6)",
    "audit": "T-052 (P6)",
    "sample-run": "T-051 (P6)",
    "build-handoff": "T-015 / H1 (11_HANDOFF §2)",
    "verify-handoff": "H1..H3 (11_HANDOFF §5)",
    # Zadania klastrowe: Makefile blokuje je wczesniej, ale gdyby ktos wywolal
    # CLI bezposrednio, komunikat ma byc taki sam.
    "tag-ctrl": "T-015 / H1 — zadanie klastrowe",
    "variance-array": "T-035 / H2 — zadanie klastrowe",
    "av-train": "T-038, T-039 / H2 — zadanie klastrowe",
    "embed": "T-048 / H3 — zadanie klastrowe",
}


class StageNotImplementedError(RuntimeError):
    """Etap nalezy do pozniejszej fazy backlogu."""


def _load(args: argparse.Namespace) -> Config:
    overlays = [Path(p) for p in (args.overlay or [])]
    return load_config(Path(args.config), overlays=overlays)


# --------------------------------------------------------------------------
# Podkomendy P0
# --------------------------------------------------------------------------


def cmd_hash_config(args: argparse.Namespace) -> int:
    config = _load(args)
    print(config.config_hash())
    return EXIT_OK


def cmd_show_config(args: argparse.Namespace) -> int:
    import json

    config = _load(args)
    print(json.dumps(config.hashable_payload(), ensure_ascii=False, indent=2, sort_keys=True))
    return EXIT_OK


def cmd_init_env(args: argparse.Namespace) -> int:
    """Tworzy `configs/env.local.yaml` z HOST_ROLE=laptop (11_HANDOFF §6).

    Plik jest poza gitem. Agent nie ma jak przelaczyc sie na `cluster`, bo nie
    ma tam dostepu — na klastrze robisz to recznie.
    """
    path = Path(args.path) if args.path else ENV_LOCAL_PATH
    if path.exists() and not args.force:
        print(f"{path} juz istnieje — zostawiam bez zmian (uzyj --force, zeby nadpisac).")
        return EXIT_OK
    write_yaml(path, {"host_role": "laptop"})
    print(f"Zapisano {path} (host_role: laptop).")
    return EXIT_OK


def cmd_verify_sources(args: argparse.Namespace) -> int:
    from src.data.verify_sources import (
        RequestsFetcher,
        load_sources,
        verify_sources,
    )
    from src.utils.runs import log_blocker, log_run

    config = _load(args)
    sources = load_sources(Path(args.sources))
    report = verify_sources(sources, RequestsFetcher())

    out_path = Path(args.out) if args.out else SOURCE_CHECK_PATH
    write_json(out_path, report.model_dump(mode="json"))

    for check in report.sources:
        marker = {"ok": "OK      ", "degraded": "DEGRADED", "fail": "FAIL    "}[check.status]
        print(f"{marker} {check.id:<20} {check.title}")
        for note in check.notes:
            print(f"         - {note}")

    print(f"\nOverall: {report.overall.upper()}  ->  {out_path}")

    failed = report.failed_required()
    for check in failed:
        # AGENTS.md: niedostepne zrodlo albo niezgodny format to jeden z czterech
        # przypadkow "zatrzymaj sie i zapytaj". Zapisujemy pytanie, nie zgadujemy.
        log_blocker(
            task="verify-sources",
            question=(
                f"Zrodlo '{check.id}' ({check.title}) nie przeszlo weryfikacji. "
                f"Uwagi: {'; '.join(check.notes) or 'brak'}. "
                "Czy uzywamy innego adresu/wersji, czy wstrzymujemy P1?"
            ),
            context=(
                f"{check.decision_ref} | zaobserwowano: {check.resolved} | "
                f"brakujace kolumny: {check.columns_missing}"
            ),
            source=check.url or "",
            artifacts=[rel_to_repo(out_path)],
        )

    log_run(
        task="verify-sources",
        status="blocked" if failed else "done",
        config_hash=config.config_hash(),
        artifacts=[rel_to_repo(out_path)],
        metrics={
            "n_sources": len(report.sources),
            "n_ok": sum(1 for s in report.sources if s.status == "ok"),
            "n_degraded": sum(1 for s in report.sources if s.status == "degraded"),
            "n_fail": sum(1 for s in report.sources if s.status == "fail"),
        },
        note=f"overall={report.overall}",
    )
    return EXIT_BLOCKED if failed else EXIT_OK


def cmd_figs_smoke(args: argparse.Namespace) -> int:
    from src.utils.runs import log_run
    from src.viz.fig00_smoke import run as run_smoke

    config = _load(args)
    saved = run_smoke(config)
    artifacts = [rel_to_repo(p) for p in (saved.png, saved.svg, saved.json, saved.index)]
    for path in artifacts:
        print(f"zapisano {path}")

    log_run(
        task="T-008",
        status="done",
        config_hash=config.config_hash(),
        artifacts=artifacts,
        metrics={"n_files": 3},
        note="make figs-smoke",
    )
    return EXIT_OK


def cmd_freeze(args: argparse.Namespace) -> int:
    """`make freeze` musi zawiesc, jesli `make gates` nie byl uruchomiony
    na aktualnym configu (08_REPO.md §6)."""
    config = _load(args)
    gates_path = RESULTS_DIR / "gates.json"

    if not gates_path.exists():
        print(
            "BLOCKED: brak results/gates.json. FREEZE (T-033) wymaga wczesniejszego "
            "`make gates` (T-029..T-032) na aktualnym configu.",
            file=sys.stderr,
        )
        return EXIT_FAIL

    from src.utils.io import read_json

    gates = read_json(gates_path)
    if gates.get("config_hash") != config.config_hash():
        print(
            "BLOCKED: results/gates.json pochodzi z innego configu "
            f"({gates.get('config_hash')} != {config.config_hash()}). "
            "Uruchom `make gates` ponownie.",
            file=sys.stderr,
        )
        return EXIT_FAIL

    raise StageNotImplementedError("T-033 (P4)")


def cmd_main(args: argparse.Namespace) -> int:
    """`make main` musi zawiesc bez configs/frozen/ (AGENTS.md zasada 2)."""
    frozen = sorted(FROZEN_CONFIG_DIR.glob("*.yaml")) if FROZEN_CONFIG_DIR.exists() else []
    if not frozen:
        print(
            "BLOCKED: configs/frozen/ jest puste. Nie wolno liczyc niczego na Koranie "
            "przed FREEZE (T-033). Uruchom najpierw `make gates`, potem `make freeze`.",
            file=sys.stderr,
        )
        return EXIT_FAIL
    raise StageNotImplementedError("T-034..T-042 (P5)")


def cmd_pending(args: argparse.Namespace) -> int:
    raise StageNotImplementedError(PENDING_STAGES[args.command])


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------


def _add_config_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="sciezka do configu bazowego")
    parser.add_argument(
        "--overlay",
        action="append",
        default=[],
        help="nakladka na config (mozna podac wielokrotnie, kolejnosc ma znaczenie)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="quran-stylometry — CLI. Kolejnosc etapow: docs/08_REPO.md §6.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_hash = sub.add_parser("hash-config", help="deterministyczny sha256 zwalidowanego configu")
    _add_config_args(p_hash)
    p_hash.set_defaults(func=cmd_hash_config)

    p_show = sub.add_parser("show-config", help="zwalidowany config jako kanoniczny JSON")
    _add_config_args(p_show)
    p_show.set_defaults(func=cmd_show_config)

    p_env = sub.add_parser("init-env", help="tworzy configs/env.local.yaml (HOST_ROLE=laptop)")
    p_env.add_argument("--path", default=None)
    p_env.add_argument("--force", action="store_true")
    p_env.set_defaults(func=cmd_init_env)

    p_vs = sub.add_parser("verify-sources", help="sprawdza zrodla z 09_DECISIONS §2")
    _add_config_args(p_vs)
    p_vs.add_argument("--sources", default=str(DEFAULT_SOURCES))
    p_vs.add_argument("--out", default=str(SOURCE_CHECK_PATH))
    p_vs.set_defaults(func=cmd_verify_sources)

    p_smoke = sub.add_parser("figs-smoke", help="generuje figure testowa z pelnym kompletem plikow")
    _add_config_args(p_smoke)
    p_smoke.set_defaults(func=cmd_figs_smoke)

    p_freeze = sub.add_parser("freeze", help="T-033 FREEZE (wymaga wczesniejszego `make gates`)")
    _add_config_args(p_freeze)
    p_freeze.set_defaults(func=cmd_freeze)

    p_main = sub.add_parser("main", help="wynik glowny (wymaga configs/frozen/)")
    _add_config_args(p_main)
    p_main.set_defaults(func=cmd_main)

    for stage in PENDING_STAGES:
        if stage in {"freeze", "main"}:
            continue
        p_stage = sub.add_parser(stage, help=f"etap zaplanowany: {PENDING_STAGES[stage]}")
        _add_config_args(p_stage)
        p_stage.add_argument("--job", default=None)
        p_stage.add_argument("--out", default=None)
        p_stage.add_argument("--strict", action="store_true")
        p_stage.set_defaults(func=cmd_pending)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    ensure_dir(RESULTS_DIR)
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except StageNotImplementedError as exc:
        print(
            f"NIEZAIMPLEMENTOWANE: etap '{args.command}' nalezy do {exc}. "
            "Zakres tej fazy: docs/07_TASKS.md.",
            file=sys.stderr,
        )
        return EXIT_NOT_IMPLEMENTED


if __name__ == "__main__":
    raise SystemExit(main())
