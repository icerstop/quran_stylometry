"""T-005 — rejestr przebiegow i blockerow.

Kluczowa regula, ktorej broni ten plik: `status="blocked"` bez wpisu
w `blockers.jsonl` z polem `question` jest bledem (AGENTS.md), a nie
dopuszczalnym skrotem.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.utils.io import read_jsonl
from src.utils.runs import (
    MissingBlockerError,
    RunRecord,
    has_blocker,
    log_blocker,
    log_run,
    read_runs,
    resolve_blockers,
)


@pytest.fixture
def logs(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "runs.jsonl", tmp_path / "blockers.jsonl"


def test_run_record_has_required_fields(logs: tuple[Path, Path]) -> None:
    runs_path, blockers_path = logs
    record = log_run(
        "T-014",
        "done",
        config_hash="abc123",
        artifacts=["results/tagger_eval.json"],
        metrics={"pos_accuracy": 0.83},
        path=runs_path,
        blockers_path=blockers_path,
    )

    assert record.task == "T-014"
    assert record.status == "done"
    assert record.host == "laptop"
    assert record.ts

    written = list(read_jsonl(runs_path))
    assert len(written) == 1
    for field in ("task", "status", "config_hash", "git_sha", "artifacts", "metrics", "host"):
        assert field in written[0]


def test_appends_do_not_overwrite(logs: tuple[Path, Path]) -> None:
    runs_path, blockers_path = logs
    for task in ("T-001", "T-002", "T-003"):
        log_run(task, "done", path=runs_path, blockers_path=blockers_path)
    assert [r.task for r in read_runs(runs_path)] == ["T-001", "T-002", "T-003"]


def test_blocked_without_blocker_entry_is_rejected(logs: tuple[Path, Path]) -> None:
    runs_path, blockers_path = logs
    with pytest.raises(MissingBlockerError):
        log_run("T-011", "blocked", path=runs_path, blockers_path=blockers_path)
    assert not runs_path.exists()


def test_blocked_with_blocker_entry_is_accepted(logs: tuple[Path, Path]) -> None:
    runs_path, blockers_path = logs
    log_blocker(
        "T-011",
        "Selekcja daje 41 autorow zamiast 60. Poluzowac prog czy poszerzyc zakres AH?",
        path=blockers_path,
    )
    assert has_blocker("T-011", path=blockers_path)

    record = log_run("T-011", "blocked", path=runs_path, blockers_path=blockers_path)
    assert record.status == "blocked"


def test_blocker_requires_nonempty_question(logs: tuple[Path, Path]) -> None:
    _, blockers_path = logs
    with pytest.raises(ValidationError):
        log_blocker("T-011", "   ", path=blockers_path)


def test_awaiting_cluster_is_a_valid_status(logs: tuple[Path, Path]) -> None:
    """11_HANDOFF §4: po zbudowaniu paczki agent wpisuje `awaiting_cluster`."""
    runs_path, blockers_path = logs
    record = log_run(
        "T-015", "awaiting_cluster", host="cluster", path=runs_path, blockers_path=blockers_path
    )
    assert record.status == "awaiting_cluster"
    assert record.host == "cluster"


def test_git_sha_is_never_invented(logs: tuple[Path, Path]) -> None:
    """Brak repo/commita ma dac `None` plus powod, nigdy syntetyczny hash."""
    runs_path, blockers_path = logs
    record = log_run("T-001", "done", path=runs_path, blockers_path=blockers_path)
    if record.git_sha is None:
        assert record.git_state == "no-commit-or-no-repo"
    else:
        assert len(record.git_sha) == 40
        assert record.git_state is None


def test_resolve_blockers_marks_entry_without_deleting_it(logs: tuple[Path, Path]) -> None:
    """AGENTS.md: log jest append-only — domkniecie dopisuje, nigdy nie usuwa."""
    _, blockers_path = logs
    log_blocker("T-009", "Pytanie 1", path=blockers_path)
    log_blocker("T-009", "Pytanie 2", path=blockers_path)
    log_blocker("T-011", "Inne zadanie, nie powinno sie zmienic", path=blockers_path)

    changed = resolve_blockers(
        "T-009", "Rozstrzygniete w 09_DECISIONS.md §2.1.", path=blockers_path
    )
    assert changed == 2

    entries = list(read_jsonl(blockers_path))
    assert len(entries) == 3
    t009_entries = [e for e in entries if e["task"] == "T-009"]
    assert all(e["resolved"] is True for e in t009_entries)
    assert all(e["resolution"] == "Rozstrzygniete w 09_DECISIONS.md §2.1." for e in t009_entries)
    assert all(e["resolved_ts"] for e in t009_entries)
    assert {e["question"] for e in t009_entries} == {"Pytanie 1", "Pytanie 2"}

    other = next(e for e in entries if e["task"] == "T-011")
    assert other["resolved"] is False
    assert other["resolution"] == ""


def test_resolve_blockers_is_idempotent_for_already_resolved_entries(
    logs: tuple[Path, Path],
) -> None:
    _, blockers_path = logs
    log_blocker("T-009", "Pytanie", path=blockers_path)
    resolve_blockers("T-009", "Pierwsza odpowiedz.", path=blockers_path)
    changed_again = resolve_blockers("T-009", "Druga odpowiedz.", path=blockers_path)

    assert changed_again == 0
    entry = next(iter(read_jsonl(blockers_path)))
    assert entry["resolution"] == "Pierwsza odpowiedz."


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RunRecord(task="T-001", status="probably_fine")  # type: ignore[arg-type]


def test_jsonl_lines_are_valid_json(logs: tuple[Path, Path]) -> None:
    runs_path, blockers_path = logs
    log_run(
        "T-001",
        "done",
        note="uwaga z polskimi znakami: zrodlo",
        path=runs_path,
        blockers_path=blockers_path,
    )
    for line in runs_path.read_text(encoding="utf-8").splitlines():
        json.loads(line)
