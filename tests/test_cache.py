"""T-006 — cache macierzy cech.

DoD: drugie wywolanie nie przelicza. Pulapka z 07_TASKS.md: klucz MUSI zawierac
wersje normalizatora i taggera — tu sprawdzone wprost, przez porownanie kluczy
roznacych sie tylko ta wersja.

Wszystko dzieje sie w `tmp_path`; test nigdy nie pisze do `data/`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.utils.cache import (
    CacheIntegrityError,
    CacheKey,
    cache_dir,
    get_or_compute,
    is_cached,
    load,
    store,
)


def make_key(**overrides: str) -> CacheKey:
    defaults = {
        "family": "character",
        "config_hash": "cfg0000000000",
        "corpus_id": "ctrl_train",
        "normalizer_version": "strict-1.0.0",
        "tagger_version": "camel-tools-1.6.0",
    }
    defaults.update(overrides)
    return CacheKey(**defaults)  # type: ignore[arg-type]


def make_payload(n_rows: int = 6, n_cols: int = 4) -> tuple[np.ndarray, pd.DataFrame]:
    matrix = np.arange(n_rows * n_cols, dtype=np.float64).reshape(n_rows, n_cols)
    index = pd.DataFrame({"document_id": [f"doc_{i:03d}" for i in range(n_rows)]})
    return matrix, index


def test_second_call_does_not_recompute(tmp_path: Path) -> None:
    key = make_key()
    calls = {"n": 0}

    def compute() -> tuple[np.ndarray, pd.DataFrame]:
        calls["n"] += 1
        return make_payload()

    first = get_or_compute(key, compute, root=tmp_path)
    second = get_or_compute(key, compute, root=tmp_path)

    assert calls["n"] == 1, "Drugie wywolanie przeliczylo macierz — cache nie dziala"
    assert first.from_cache is False
    assert second.from_cache is True
    np.testing.assert_array_equal(first.matrix, second.matrix)
    pd.testing.assert_frame_equal(first.index, second.index)


def test_force_recomputes(tmp_path: Path) -> None:
    key = make_key()
    calls = {"n": 0}

    def compute() -> tuple[np.ndarray, pd.DataFrame]:
        calls["n"] += 1
        return make_payload()

    get_or_compute(key, compute, root=tmp_path)
    get_or_compute(key, compute, root=tmp_path, force=True)
    assert calls["n"] == 2


@pytest.mark.parametrize(
    "field",
    ["family", "config_hash", "corpus_id", "normalizer_version", "tagger_version"],
)
def test_every_key_component_changes_the_fingerprint(field: str) -> None:
    base = make_key()
    changed = make_key(**{field: "inna-wartosc"})
    assert base.fingerprint() != changed.fingerprint(), (
        f"Zmiana '{field}' nie zmienia odcisku klucza — "
        "przemieszanie artefaktow byloby niewykrywalne"
    )


def test_normalizer_and_tagger_versions_split_the_cache(tmp_path: Path) -> None:
    """Zmiana normalizatora musi wymusic przeliczenie, nie podac starej macierzy."""
    calls = {"n": 0}

    def compute() -> tuple[np.ndarray, pd.DataFrame]:
        calls["n"] += 1
        return make_payload()

    get_or_compute(make_key(), compute, root=tmp_path)
    get_or_compute(make_key(normalizer_version="strict-2.0.0"), compute, root=tmp_path)
    get_or_compute(make_key(tagger_version="camel-tools-9.9.9"), compute, root=tmp_path)
    assert calls["n"] == 3


def test_meta_records_versions_explicitly(tmp_path: Path) -> None:
    key = make_key()
    matrix, index = make_payload()
    store(key, matrix, index, root=tmp_path)
    cached = load(key, root=tmp_path)

    assert cached.meta["normalizer_version"] == "strict-1.0.0"
    assert cached.meta["tagger_version"] == "camel-tools-1.6.0"
    assert cached.meta["n_rows"] == matrix.shape[0]
    assert cached.meta["n_cols"] == matrix.shape[1]


def test_row_count_mismatch_is_rejected(tmp_path: Path) -> None:
    matrix, index = make_payload(n_rows=6)
    with pytest.raises(CacheIntegrityError):
        store(make_key(), matrix, index.head(3), root=tmp_path)


def test_tampered_meta_is_detected(tmp_path: Path) -> None:
    """Podmiana metadanych (np. przez recznego rsynca) ma dac blad, nie cichy wynik."""
    key = make_key()
    matrix, index = make_payload()
    store(key, matrix, index, root=tmp_path)

    meta_path = cache_dir(key, root=tmp_path) / "meta.json"
    meta_path.write_text(
        meta_path.read_text(encoding="utf-8").replace(key.fingerprint(), "0" * 64),
        encoding="utf-8",
    )
    with pytest.raises(CacheIntegrityError):
        load(key, root=tmp_path)


def test_is_cached_false_before_store(tmp_path: Path) -> None:
    assert is_cached(make_key(), root=tmp_path) is False
