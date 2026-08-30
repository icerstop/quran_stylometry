"""Logi strukturalne (T-005).

Jeden format dla laptopa i klastra: JSON na stderr. Logi z klastra wracaja jako
ogon pliku `.out` i musza dac sie sparsowac bez zgadywania, gdzie konczy sie
komunikat, a zaczyna traceback.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

_CONFIGURED = False

_RESERVED = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def setup_logging(level: int | None = None) -> None:
    """Konfiguruje handler raz na proces. Poziom przez QS_LOG_LEVEL."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    if level is None:
        level = getattr(logging, os.environ.get("QS_LOG_LEVEL", "INFO").upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
