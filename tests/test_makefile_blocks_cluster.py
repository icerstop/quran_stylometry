"""11_HANDOFF §6 — Makefile blokuje zadania klastrowe lokalnie.

Test czyta Makefile jako tekst, bo o to wlasnie chodzi: mechanizm ma dzialac
zanim ktokolwiek uruchomi Pythona. Gdyby ktos usunal strażnika `HOST_ROLE`
przy refaktorze, agent bez dostepu do klastra probowalby policzyc T-015 lokalnie.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.cli import PENDING_STAGES, build_parser
from src.config import EnvLocal, load_env_local

CLUSTER_TASKS = ("tag-ctrl", "variance-array", "av-train", "embed")


@pytest.fixture(scope="module")
def makefile(repo_root: Path) -> str:
    return (repo_root / "Makefile").read_text(encoding="utf-8")


def test_host_role_defaults_to_laptop(makefile: str) -> None:
    assert re.search(r"^HOST_ROLE\s*\?=\s*laptop\s*$", makefile, re.MULTILINE)


def test_cluster_tasks_list_matches_handoff_doc(makefile: str) -> None:
    match = re.search(r"^CLUSTER_TASKS\s*:=\s*(.+)$", makefile, re.MULTILINE)
    assert match, "Brak listy CLUSTER_TASKS w Makefile"
    assert tuple(match.group(1).split()) == CLUSTER_TASKS


def test_cluster_target_is_guarded_and_exits_nonzero(makefile: str) -> None:
    block = makefile.split("$(CLUSTER_TASKS):", 1)
    assert len(block) == 2, "Brak reguly dla $(CLUSTER_TASKS)"
    guarded = block[1]
    assert "ifneq ($(HOST_ROLE),cluster)" in guarded
    assert "BLOCKED" in guarded
    assert "@exit 1" in guarded
    assert "make handoff" in guarded


def test_handoff_targets_exist(makefile: str) -> None:
    assert re.search(r"^handoff:", makefile, re.MULTILINE)
    assert re.search(r"^handoff-verify:", makefile, re.MULTILINE)
    assert "--strict" in makefile


def test_all_documented_targets_exist(makefile: str) -> None:
    """Lista z docs/08_REPO.md §6 plus targety wymagane przez P0."""
    required = [
        "setup",
        "data",
        "normalize",
        "tag",
        "clean-quotes",
        "segment",
        "features",
        "gates",
        "freeze",
        "main",
        "chrono",
        "explore",
        "figs",
        "dashboard",
        "audit",
        "test",
        "verify-sources",
        "figs-smoke",
    ]
    for target in required:
        assert re.search(
            rf"^{re.escape(target)}:", makefile, re.MULTILINE
        ), f"Brak targetu {target}"


def test_recipes_avoid_posix_only_shell_constructs(makefile: str) -> None:
    """Recipe musza dzialac i pod /bin/sh, i pod cmd.exe (GNU Make na Windowsie)."""
    for line in makefile.splitlines():
        if not line.startswith("\t"):
            continue
        recipe = line.lstrip("\t").lstrip("@-")
        assert not recipe.startswith("source "), f"`source` nie istnieje w cmd.exe: {line!r}"
        assert "&&" not in recipe, f"Lancuch `&&` w recipe jest nieprzenosny: {line!r}"


def test_camel_data_is_wired_into_the_makefile(makefile: str) -> None:
    """Pulapka z T-001: camel-tools wymaga pobrania danych — ujac w Makefile."""
    assert "camel_data -i light" in makefile


def test_cli_exposes_every_cluster_task(makefile: str) -> None:
    """Gdyby ktos wywolal CLI z pominieciem Make, komunikat ma byc taki sam."""
    parser = build_parser()
    for task in CLUSTER_TASKS:
        assert task in PENDING_STAGES
        assert parser.parse_args([task]).command == task


def test_env_local_defaults_to_laptop_when_absent(tmp_path: Path) -> None:
    assert load_env_local(tmp_path / "nie_ma.yaml").host_role == "laptop"
    assert EnvLocal().host_role == "laptop"


def test_env_local_is_gitignored(repo_root: Path) -> None:
    assert "configs/env.local.yaml" in (repo_root / ".gitignore").read_text(encoding="utf-8")
