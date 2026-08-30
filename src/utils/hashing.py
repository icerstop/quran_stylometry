"""Hashowanie deterministyczne (T-002, T-005, T-006).

Jedno miejsce, w ktorym powstaja wszystkie hashe w projekcie. Kanonizacja JSON-a
jest tu istotna: `config_hash` musi byc niezalezny od formatowania pliku YAML,
od kolejnosci kluczy i od `PYTHONHASHSEED`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_CHUNK = 1 << 20


def canonical_json(payload: Any) -> str:
    """Zwraca kanoniczna reprezentacje JSON: klucze posortowane, bez spacji.

    `sort_keys=True` jest tym, co czyni hash niezaleznym od kolejnosci wpisow
    w YAML-u. `ensure_ascii=False` + jawne UTF-8 przy kodowaniu, zeby tresci
    arabskie nie zmienialy hasha zaleznie od ustawien srodowiska.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=_json_default,
    )


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Path):
        return obj.as_posix()
    if isinstance(obj, set | frozenset):
        return sorted(obj)
    if isinstance(obj, tuple):
        return list(obj)
    raise TypeError(f"Typ nieserializowalny do kanonicznego JSON-a: {type(obj)!r}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_json(payload: Any) -> str:
    """sha256 kanonicznego JSON-a — podstawa `config_hash`."""
    return sha256_text(canonical_json(payload))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def short_hash(full_hash: str, length: int = 12) -> str:
    """Skrocony hash do nazw katalogow cache i plikow modeli."""
    if length <= 0 or length > len(full_hash):
        raise ValueError(f"Nieprawidlowa dlugosc skrotu: {length}")
    return full_hash[:length]
