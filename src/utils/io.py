"""I/O z jawnym kodowaniem i walidacja przy zapisie/odczycie (T-007).

Wszystkie operacje wymuszaja UTF-8 i `newline=""` dla CSV — inaczej ten sam kod
daje rozne pliki na Windowsie i na klastrze, co psuje hashe artefaktow.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from src.utils.hashing import canonical_json


class SchemaViolationError(ValueError):
    """Rekord nie spelnia kontraktu I/O z docs/03_DATA.md §9."""


def ensure_dir(path: Path) -> Path:
    """Tworzy katalog (rekurencyjnie) i zwraca go.

    Katalogi robocze w `data/` powstaja wylacznie tedy, w runtime — repo nie
    zawiera zadnych plikow w `data/` poza `data/reference/`.
    """
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise SchemaViolationError(f"{path} nie zawiera mapowania YAML, tylko {type(loaded)!r}")
    return loaded


def write_yaml(path: Path, payload: dict[str, Any]) -> Path:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=True)
    return path


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any, *, indent: int = 2) -> Path:
    """Zapis JSON-a czytelnego dla czlowieka, ale z posortowanymi kluczami.

    Sortowanie kluczy jest celowe: diff dwoch artefaktow ma pokazywac roznice
    wartosci, nie roznice kolejnosci.
    """
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=indent, sort_keys=True)
        handle.write("\n")
    return path


def append_jsonl(path: Path, record: dict[str, Any]) -> Path:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(record) + "\n")
    return path


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise SchemaViolationError(f"{path}:{line_no} nie jest poprawnym JSON-em") from exc
            yield parsed


def write_model(path: Path, model: BaseModel) -> Path:
    """Zapis modelu pydantic z walidacja po stronie zapisu."""
    return write_json(path, model.model_dump(mode="json"))


def read_model[ModelT: BaseModel](path: Path, model_cls: type[ModelT]) -> ModelT:
    """Odczyt z walidacja — kontrakt sprawdzany w obie strony (T-007 DoD)."""
    raw = read_json(path)
    try:
        return model_cls.model_validate(raw)
    except ValidationError as exc:
        raise SchemaViolationError(f"{path} nie spelnia kontraktu {model_cls.__name__}") from exc


def write_models_jsonl(path: Path, models: Iterable[BaseModel]) -> Path:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for model in models:
            handle.write(canonical_json(model.model_dump(mode="json")) + "\n")
    return path


def read_models_jsonl[ModelT: BaseModel](path: Path, model_cls: type[ModelT]) -> Iterator[ModelT]:
    for line_no, record in enumerate(read_jsonl(path), start=1):
        try:
            yield model_cls.model_validate(record)
        except ValidationError as exc:
            raise SchemaViolationError(
                f"{path}:{line_no} nie spelnia kontraktu {model_cls.__name__}"
            ) from exc
