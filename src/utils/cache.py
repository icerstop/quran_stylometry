"""Cache macierzy cech (T-006).

Klucz: `(family, config_hash, corpus_id)`. Pulapka z 07_TASKS.md i 10_COMPUTE.md §3
mowi, ze klucz MUSI zawierac wersje normalizatora i taggera — spelnione przez
konstrukcje: `config_hash` jest hashem calego zwalidowanego configu, wiec
`normalizer.version` i `tagger.version` sa w nim zawarte. Dodatkowo obie wersje
laduja jawnie w `meta.json`, zeby pomieszanie artefaktow z dwoch srodowisk bylo
wykrywalne przy ogladaniu pliku, a nie dopiero przy debugowaniu wyniku.

Uklad na dysku (08_REPO.md §1):
    data/features/<family>/<config_hash>/{matrix.npz,index.parquet,meta.json}
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.paths import DATA_FEATURES_DIR
from src.utils.hashing import sha256_json
from src.utils.io import ensure_dir, read_json, write_json
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)

MATRIX_FILENAME = "matrix.npz"
INDEX_FILENAME = "index.parquet"
META_FILENAME = "meta.json"


class CacheIntegrityError(RuntimeError):
    """Wpis w cache istnieje, ale jego metadane nie zgadzaja sie z zadanym kluczem."""


@dataclass(frozen=True)
class CacheKey:
    family: str
    config_hash: str
    corpus_id: str
    normalizer_version: str
    tagger_version: str

    def to_dict(self) -> dict[str, str]:
        return {
            "family": self.family,
            "config_hash": self.config_hash,
            "corpus_id": self.corpus_id,
            "normalizer_version": self.normalizer_version,
            "tagger_version": self.tagger_version,
        }

    def fingerprint(self) -> str:
        return sha256_json(self.to_dict())


@dataclass(frozen=True)
class CachedMatrix:
    matrix: np.ndarray
    index: pd.DataFrame
    meta: dict[str, Any]
    from_cache: bool


def cache_dir(key: CacheKey, *, root: Path = DATA_FEATURES_DIR) -> Path:
    """Sciezka wpisu. Nazwa liscia niesie CALY klucz, nie sam `config_hash`.

    W normalnym uzyciu `config_hash` juz zawiera `normalizer.version` i
    `tagger.version`, bo jest hashem calego configu. Ale `CacheKey` przyjmuje te
    wersje osobno, wiec bez odcisku w nazwie dwa rozne klucze mogłyby wskazac ten
    sam katalog — a wtedy niezgodnosc wychodzi dopiero jako blad integralnosci
    przy odczycie, zamiast po prostu nie trafic w cache.
    """
    return root / key.family / key.corpus_id / f"{key.config_hash}-{key.fingerprint()[:12]}"


def is_cached(key: CacheKey, *, root: Path = DATA_FEATURES_DIR) -> bool:
    target = cache_dir(key, root=root)
    return all(
        (target / name).exists() for name in (MATRIX_FILENAME, INDEX_FILENAME, META_FILENAME)
    )


def store(
    key: CacheKey,
    matrix: np.ndarray,
    index: pd.DataFrame,
    *,
    extra_meta: dict[str, Any] | None = None,
    root: Path = DATA_FEATURES_DIR,
) -> Path:
    if matrix.shape[0] != len(index):
        raise CacheIntegrityError(
            f"Liczba wierszy macierzy ({matrix.shape[0]}) != dlugosc indeksu ({len(index)})"
        )

    target = ensure_dir(cache_dir(key, root=root))
    np.savez_compressed(target / MATRIX_FILENAME, matrix=matrix)
    index.to_parquet(target / INDEX_FILENAME, index=False)

    meta: dict[str, Any] = {
        **key.to_dict(),
        "fingerprint": key.fingerprint(),
        "n_rows": int(matrix.shape[0]),
        "n_cols": int(matrix.shape[1]) if matrix.ndim > 1 else 1,
        "dtype": str(matrix.dtype),
    }
    if extra_meta:
        meta.update(extra_meta)
    write_json(target / META_FILENAME, meta)
    return target


def load(key: CacheKey, *, root: Path = DATA_FEATURES_DIR) -> CachedMatrix:
    target = cache_dir(key, root=root)
    meta = read_json(target / META_FILENAME)

    if meta.get("fingerprint") != key.fingerprint():
        raise CacheIntegrityError(
            f"Odcisk klucza w {target / META_FILENAME} nie zgadza sie z zadanym kluczem. "
            "Najczestsza przyczyna: przemieszanie artefaktow z laptopa i klastra."
        )

    with np.load(target / MATRIX_FILENAME) as payload:
        matrix = payload["matrix"]
    index = pd.read_parquet(target / INDEX_FILENAME)
    return CachedMatrix(matrix=matrix, index=index, meta=meta, from_cache=True)


def get_or_compute(
    key: CacheKey,
    compute: Callable[[], tuple[np.ndarray, pd.DataFrame]],
    *,
    extra_meta: dict[str, Any] | None = None,
    root: Path = DATA_FEATURES_DIR,
    force: bool = False,
) -> CachedMatrix:
    """Zwraca macierz z cache albo liczy ja raz i zapisuje.

    DoD T-006: drugie wywolanie nie przelicza.
    """
    if not force and is_cached(key, root=root):
        LOGGER.info("cache hit", extra={"family": key.family, "corpus_id": key.corpus_id})
        return load(key, root=root)

    LOGGER.info("cache miss", extra={"family": key.family, "corpus_id": key.corpus_id})
    matrix, index = compute()
    store(key, matrix, index, extra_meta=extra_meta, root=root)
    return CachedMatrix(
        matrix=matrix,
        index=index,
        meta=read_json(cache_dir(key, root=root) / META_FILENAME),
        from_cache=False,
    )
