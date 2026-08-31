"""T-011 — metadane i selektywne pobranie tekstow OpenITI.

09_DECISIONS.md §2.3: najpierw sam TSV metadanych z Zenodo (wersja pinowana
w `results/source_check.json`), potem pojedyncze pliki przez
`raw.githubusercontent.com` z repozytoriow 25-letnich. Nie klonujemy release
(2,27 mld slow / ~6 GB zip).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.paths import CONFIGS_DIR, DATA_RAW_DIR
from src.utils.io import ensure_dir, read_json, read_yaml
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)

RAW_OPENITI_DIR: Path = DATA_RAW_DIR / "openiti"
METADATA_FILENAME = "OpenITI_metadata_2025-1-9.tsv"
DEFAULT_METADATA_PATH: Path = RAW_OPENITI_DIR / METADATA_FILENAME

# language w TSV to ISO 639-3 `ara`, nie `ar` z 09_DECISIONS.md §3.
# `ara` jest jednoznacznym kodem arabskiego — nie zgadujemy, tylko mapujemy.
ARABIC_LANGUAGE_CODES = frozenset({"ara", "ar"})

ZENODO_METADATA_URL = (
    "https://zenodo.org/api/records/17767721/files/"
    f"{METADATA_FILENAME}/content"
)


def metadata_path() -> Path:
    return DEFAULT_METADATA_PATH


def download_metadata(*, dest: Path = DEFAULT_METADATA_PATH, force: bool = False) -> Path:
    if dest.exists() and not force:
        return dest
    ensure_dir(dest.parent)
    LOGGER.info("pobieram metadane OpenITI", extra={"url": ZENODO_METADATA_URL})
    with requests.get(ZENODO_METADATA_URL, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        with dest.open("wb") as handle:
            for chunk in resp.iter_content(1 << 16):
                handle.write(chunk)
    return dest


def load_metadata(path: Path | None = None) -> pd.DataFrame:
    target = path or metadata_path()
    df = pd.read_csv(target, sep="\t", dtype=str, keep_default_na=False)
    df["death_date_ah"] = pd.to_numeric(df["date"], errors="coerce")
    df["tok_length_n"] = pd.to_numeric(df["tok_length"], errors="coerce")
    df["author_id"] = df["book"].str.split(".", n=1).str[0]
    df["has_cleaned_tag"] = df["tags"].str.contains("CLEANED_VERSION", regex=False)
    df["is_arabic"] = df["language"].isin(ARABIC_LANGUAGE_CODES)
    df["is_pri"] = df["status"].str.lower() == "pri"
    df["uncorrected_ocr"] = df["uncorrected_OCR"].str.lower() == "true"
    return df


def repo_for_death_date(death_date_ah: int) -> str:
    """Repozytorium 25-letnie OpenITI: 0025AH, 0050AH, ..., 0900AH."""
    if death_date_ah <= 0:
        raise ValueError(f"death_date_ah musi byc > 0, dostano {death_date_ah}")
    bucket = ((int(death_date_ah) + 24) // 25) * 25
    return f"{bucket:04d}AH"


def raw_text_url(row: pd.Series, *, branch: str = "master") -> str:
    """URL selektywnego pobrania: raw.githubusercontent.com / OpenITI / {25AH}."""
    death = int(row["death_date_ah"])
    repo = repo_for_death_date(death)
    rel = str(row["local_path"]).lstrip("/")
    return f"https://raw.githubusercontent.com/OpenITI/{repo}/{branch}/{rel}"


def expected_metadata_from_source_check() -> dict[str, Any]:
    """Pin wersji z ostatniego verify-sources — nie z pamieci."""
    from src.paths import SOURCE_CHECK_PATH

    report = read_json(SOURCE_CHECK_PATH)
    entry = next(s for s in report["sources"] if s["id"] == "openiti_metadata")
    return entry["resolved"]


def sources_spec() -> dict[str, Any]:
    specs = read_yaml(CONFIGS_DIR / "sources.yaml")["sources"]
    return next(s for s in specs if s["id"] == "openiti_metadata")
