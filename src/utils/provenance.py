"""Proweniencja artefaktu: git sha, host, znacznik czasu (T-005).

`git_sha` jest wyliczany, nigdy zmyslany. Brak repozytorium albo brak commita to
jawne `None` plus powod w `git_state` — AGENTS.md zasada 1 zabrania podstawiania
syntetycznego zastepnika za dane, ktore maja byc weryfikowalne.
"""

from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from src.paths import REPO_ROOT

_GIT_TIMEOUT_S = 10


@dataclass(frozen=True)
class GitState:
    sha: str | None
    dirty: bool | None
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {"git_sha": self.sha, "git_dirty": self.dirty, "git_state": self.reason}


def _run_git(args: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(  # noqa: S603
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, str(exc)
    return completed.returncode, completed.stdout.strip()


def git_state() -> GitState:
    code, sha = _run_git(["rev-parse", "HEAD"])
    if code != 0:
        return GitState(sha=None, dirty=None, reason="no-commit-or-no-repo")

    status_code, status_out = _run_git(["status", "--porcelain"])
    dirty = bool(status_out) if status_code == 0 else None
    return GitState(sha=sha, dirty=dirty, reason=None)


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def host_fingerprint() -> dict[str, str]:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
    }
