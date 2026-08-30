"""Rejestr przebiegow i blockerow (T-005).

Format wpisu jest zdefiniowany w AGENTS.md ("Format raportowania postepu").
Dwie reguly egzekwowane tutaj, a nie w dyscyplinie autora kodu:

* `status="blocked"` bez wpisu w `blockers.jsonl` jest bledem — AGENTS.md
  wprost tego wymaga, wiec `log_run` to sprawdza;
* `git_sha` pochodzi z `git rev-parse`, a jego brak jest zapisany jawnie.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.paths import BLOCKERS_LOG_PATH, RUNS_LOG_PATH
from src.utils.hashing import canonical_json
from src.utils.io import append_jsonl, read_jsonl
from src.utils.provenance import git_state, utc_now_iso

RunStatus = Literal["done", "blocked", "skipped", "awaiting_cluster", "failed"]
HostRole = Literal["laptop", "cluster"]


class MissingBlockerError(ValueError):
    """`status="blocked"` wymaga wpisu w `results/blockers.jsonl` z polem `question`."""


class RunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str
    status: RunStatus
    config_hash: str | None = None
    git_sha: str | None = None
    git_dirty: bool | None = None
    git_state: str | None = None
    artifacts: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    note: str = ""
    host: HostRole = "laptop"
    ts: str = ""

    @field_validator("task")
    @classmethod
    def _task_shape(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Pole `task` nie moze byc puste")
        return value


class BlockerRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str
    question: str
    context: str = ""
    source: str = ""
    artifacts: list[str] = Field(default_factory=list)
    ts: str = ""

    # Blocker jest domykany dopisaniem rozstrzygniecia, nigdy usunieciem wiersza
    # (log jest append-only — AGENTS.md "Format raportowania postepu").
    resolved: bool = False
    resolution: str = ""
    resolved_ts: str = ""

    @field_validator("question")
    @classmethod
    def _question_nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Blocker bez pola `question` jest bezuzyteczny dla czlowieka")
        return value


def log_blocker(
    task: str,
    question: str,
    *,
    context: str = "",
    source: str = "",
    artifacts: list[str] | None = None,
    path: Path = BLOCKERS_LOG_PATH,
) -> BlockerRecord:
    record = BlockerRecord(
        task=task,
        question=question,
        context=context,
        source=source,
        artifacts=artifacts or [],
        ts=utc_now_iso(),
    )
    append_jsonl(path, record.model_dump(mode="json"))
    return record


def has_blocker(task: str, *, path: Path = BLOCKERS_LOG_PATH) -> bool:
    return any(entry.get("task") == task for entry in read_jsonl(path))


def resolve_blockers(
    task: str,
    resolution: str,
    *,
    match: Callable[[dict[str, Any]], bool] | None = None,
    path: Path = BLOCKERS_LOG_PATH,
) -> int:
    """Domyka wpisy blockera bez ich usuwania z logu.

    Dopisuje `resolved=True`, `resolution`, `resolved_ts` do kazdego jeszcze
    nierozwiazanego wpisu o danym `task` (opcjonalnie dodatkowo zawezonego
    przez `match`), po czym zapisuje caly log na nowo — kazda linia przechodzi
    przez `BlockerRecord`, wiec format pozostaje ten sam. Zwraca liczbe
    domknietych wpisow.
    """
    if not resolution.strip():
        raise ValueError("resolve_blockers wymaga niepustego `resolution`")

    entries = list(read_jsonl(path))
    ts = utc_now_iso()
    changed = 0
    for entry in entries:
        if entry.get("task") != task or entry.get("resolved"):
            continue
        if match is not None and not match(entry):
            continue
        entry["resolved"] = True
        entry["resolution"] = resolution
        entry["resolved_ts"] = ts
        changed += 1

    if changed:
        records = [BlockerRecord.model_validate(entry) for entry in entries]
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(canonical_json(record.model_dump(mode="json")) + "\n")
    return changed


def log_run(
    task: str,
    status: RunStatus,
    *,
    config_hash: str | None = None,
    artifacts: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
    note: str = "",
    host: HostRole = "laptop",
    path: Path = RUNS_LOG_PATH,
    blockers_path: Path = BLOCKERS_LOG_PATH,
) -> RunRecord:
    if status == "blocked" and not has_blocker(task, path=blockers_path):
        raise MissingBlockerError(
            f"status='blocked' dla {task} wymaga wczesniejszego log_blocker(...) w {blockers_path}"
        )

    state = git_state()
    record = RunRecord(
        task=task,
        status=status,
        config_hash=config_hash,
        git_sha=state.sha,
        git_dirty=state.dirty,
        git_state=state.reason,
        artifacts=artifacts or [],
        metrics=metrics or {},
        note=note,
        host=host,
        ts=utc_now_iso(),
    )
    append_jsonl(path, record.model_dump(mode="json"))
    return record


def read_runs(path: Path = RUNS_LOG_PATH) -> list[RunRecord]:
    return [RunRecord.model_validate(entry) for entry in read_jsonl(path)]
