"""Wspolne fixture'y. Zaden test nie dotyka sieci ani prawdziwego `results/`."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Config
from src.paths import CONFIGS_DIR, REPO_ROOT


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def base_config_path() -> Path:
    return CONFIGS_DIR / "base.yaml"


@pytest.fixture
def config() -> Config:
    """Config z wartosciami domyslnymi — nie czyta dysku, wiec test jest stabilny."""
    return Config()
