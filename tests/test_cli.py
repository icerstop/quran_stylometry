"""CLI: bramki `make freeze` / `make main` i jawnosc etapow niezaimplementowanych.

Najwazniejsze tu: `main` musi zawiesc bez `configs/frozen/` (AGENTS.md zasada 2),
a etap z pozniejszej fazy nie moze udawac sukcesu.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.cli import EXIT_FAIL, EXIT_NOT_IMPLEMENTED, EXIT_OK, PENDING_STAGES, build_parser, main
from src.paths import CONFIGS_DIR


def test_hash_config_prints_a_sha256(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["hash-config"]) == EXIT_OK
    printed = capsys.readouterr().out.strip()
    assert len(printed) == 64
    assert all(ch in "0123456789abcdef" for ch in printed)


def test_hash_config_is_stable_between_invocations(capsys: pytest.CaptureFixture[str]) -> None:
    main(["hash-config"])
    first = capsys.readouterr().out.strip()
    main(["hash-config"])
    assert capsys.readouterr().out.strip() == first


def test_overlay_changes_the_hash(capsys: pytest.CaptureFixture[str]) -> None:
    main(["hash-config"])
    plain = capsys.readouterr().out.strip()
    main(["hash-config", "--overlay", str(CONFIGS_DIR / "laptop_only.yaml")])
    assert capsys.readouterr().out.strip() != plain


def test_main_is_blocked_without_frozen_configs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AGENTS.md zasada 2: nie liczymy niczego na Koranie przed FREEZE (T-033)."""
    monkeypatch.setattr("src.cli.FROZEN_CONFIG_DIR", tmp_path / "frozen")
    assert main(["main"]) == EXIT_FAIL
    assert "configs/frozen/" in capsys.readouterr().err


def test_freeze_is_blocked_without_gates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("src.cli.RESULTS_DIR", tmp_path)
    assert main(["freeze"]) == EXIT_FAIL
    assert "gates" in capsys.readouterr().err


def test_freeze_is_blocked_when_gates_come_from_another_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("src.cli.RESULTS_DIR", tmp_path)
    (tmp_path / "gates.json").write_text('{"config_hash": "inny_hash"}', encoding="utf-8")
    assert main(["freeze"]) == EXIT_FAIL
    assert "innego configu" in capsys.readouterr().err


@pytest.mark.parametrize("stage", sorted(PENDING_STAGES))
def test_pending_stage_fails_loudly(stage: str, capsys: pytest.CaptureFixture[str]) -> None:
    """Cichy sukces pustego etapu bylby gorszy niz jawna porazka."""
    assert main([stage]) == EXIT_NOT_IMPLEMENTED
    err = capsys.readouterr().err
    assert "NIEZAIMPLEMENTOWANE" in err
    assert PENDING_STAGES[stage] in err


def test_every_pending_stage_names_its_task() -> None:
    """Komunikat ma mowic, ktore zadanie z 07_TASKS.md odblokuje etap."""
    for stage, task in PENDING_STAGES.items():
        assert "T-" in task or "H" in task, f"{stage} nie wskazuje zadania"


def test_init_env_writes_laptop_role(tmp_path: Path) -> None:
    from src.config import load_env_local

    target = tmp_path / "env.local.yaml"
    assert main(["init-env", "--path", str(target)]) == EXIT_OK
    assert load_env_local(target).host_role == "laptop"


def test_init_env_does_not_clobber_existing_file(tmp_path: Path) -> None:
    """Na klastrze plik zawiera `cluster` — przypadkowe `make setup` nie moze go zepsuc."""
    target = tmp_path / "env.local.yaml"
    target.write_text("host_role: cluster\n", encoding="utf-8")
    assert main(["init-env", "--path", str(target)]) == EXIT_OK
    assert "cluster" in target.read_text(encoding="utf-8")


def test_subcommand_is_required() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args([])
