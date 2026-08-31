"""Kanoniczne sciezki repo.

Zadna sciezka w `src/` nie moze byc absolutna (docs/08_REPO.md §3), wiec
wszystko wyprowadzamy z jednego korzenia liczonego wzgledem tego pliku.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parent.parent

CONFIGS_DIR: Path = REPO_ROOT / "configs"
FROZEN_CONFIG_DIR: Path = CONFIGS_DIR / "frozen"
ENV_LOCAL_PATH: Path = CONFIGS_DIR / "env.local.yaml"

DATA_DIR: Path = REPO_ROOT / "data"
DATA_REFERENCE_DIR: Path = DATA_DIR / "reference"
DATA_RAW_DIR: Path = DATA_DIR / "raw"
DATA_INTERIM_DIR: Path = DATA_DIR / "interim"
DATA_PROCESSED_DIR: Path = DATA_DIR / "processed"
DATA_FEATURES_DIR: Path = DATA_DIR / "features"

RESULTS_DIR: Path = REPO_ROOT / "results"
FIGURES_DIR: Path = REPO_ROOT / "figures"
MODELS_DIR: Path = REPO_ROOT / "models"
REPORTS_DIR: Path = REPO_ROOT / "reports"
HANDOFF_DIR: Path = REPO_ROOT / "handoff"

RUNS_LOG_PATH: Path = RESULTS_DIR / "runs.jsonl"
BLOCKERS_LOG_PATH: Path = RESULTS_DIR / "blockers.jsonl"
SOURCE_CHECK_PATH: Path = RESULTS_DIR / "source_check.json"
FIGURES_INDEX_PATH: Path = FIGURES_DIR / "INDEX.md"

CHRONOLOGIES_PATH: Path = DATA_REFERENCE_DIR / "chronologies.csv"
TAG_GENRE_MAP_PATH: Path = DATA_REFERENCE_DIR / "openiti_tag_genre_map.csv"
TAGSET_MAP_PATH: Path = DATA_REFERENCE_DIR / "eqtb_camel_pos_map.csv"
GENRES_PATH: Path = DATA_REFERENCE_DIR / "genres.csv"
CTRL_MANIFEST_PATH: Path = DATA_INTERIM_DIR / "ctrl_manifest.csv"
CTRL_CAPPED_DIR: Path = DATA_INTERIM_DIR / "ctrl_capped"
CTRL_CAPPED_MANIFEST_PATH: Path = CTRL_CAPPED_DIR / "manifest.csv"
OPENITI_CLEAN_DIR: Path = DATA_INTERIM_DIR / "openiti_clean"
QUOTE_REPORT_PATH: Path = RESULTS_DIR / "quote_removal_report.json"
QUOTE_AUDIT_PATH: Path = RESULTS_DIR / "quote_audit_sample.json"
INTERNAL_DUP_PATH: Path = RESULTS_DIR / "internal_duplication.json"
OPENITI_DEDUP_DIR: Path = DATA_INTERIM_DIR / "openiti_dedup"
SEGMENTATION_REPORT_PATH: Path = RESULTS_DIR / "segmentation_report.json"
CHRONOLOGY_AGREEMENT_PATH: Path = RESULTS_DIR / "chronology_agreement.json"
SPLITS_PATH: Path = RESULTS_DIR / "splits.json"


def windows_dir(window_size: int, *, overlapping: bool = False) -> Path:
    """Katalog okien: ``data/processed/windows_{size}/`` albo ``windows_{size}_olap/``."""
    suffix = f"{int(window_size)}_olap" if overlapping else str(int(window_size))
    return DATA_PROCESSED_DIR / f"windows_{suffix}"


def rel_to_repo(path: Path | str) -> str:
    """Sciezka wzgledem korzenia repo, zawsze ze slashami.

    Uzywana wszedzie tam, gdzie sciezka trafia do artefaktu (`runs.jsonl`,
    `source_check.json`, JSON figury). Absolutna sciezka z laptopa jest w takim
    pliku bezuzyteczna dla kogokolwiek innego i rozjezdza diffy miedzy hostami.
    """
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        # Sciezka spoza repo (np. tmp_path w tescie) — zostaje jak byla.
        return resolved.as_posix()
