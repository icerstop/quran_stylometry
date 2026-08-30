"""T-009 — pobranie i sparsowanie EQTB (docs/07_TASKS.md).

Rozstrzygniecia z docs/09_DECISIONS.md §2.1 (ustalone empirycznie, session 2):

* Tabela na poziomie tokenu NIE lezy plasko w ``corpus/`` — jest spakowana w
  ``corpus/Quranic.rar`` -> ``Quranic.csv`` (UTF-16-LE, TAB). ``corpus/Quran.csv``
  (5 kolumn, poziom ajatu) NIE jest uzywany do budowy ``Window``.
* Mapowanie kolumn (40/42 zgodne werbatim; konfiguracja w ``configs/sources.yaml``):
    - ``constituent_position`` <- ``constituents_loc`` (potwierdzone, format
      ``[start-end]``, zgodny z opisem README zrodla). Mapowane 1:1.
    - ``constituent_node``: **NIEROZSTRZYGNIETE.** Zostaje kolumna
      nullable/unmapped — zadna rodzina cech (docs/04_FEATURES.md §F7) nie
      uzywa pol ``constituent_*`` (skladnia = ``rel_label`` + ``ref_token_id``).
      Patrz ``SOURCES.md`` §4.
* Wejscie do pipeline'u: kolumna ``imlaai_token`` (G2).
* Warstwa skladniowa jest czesciowo generowana parserem BiLSTM -> silver, nie
  gold (oznaczone w metadanych przez wywolujacego, nie w tym module).

Pobranie (siec) i ekstrakcja (7-Zip, subprocess) sa wstrzykiwane — tak samo jak
``Fetcher`` w ``src/data/verify_sources.py`` — zeby mapowanie kolumn i budowa
DataFrame byly testowalne bez sieci i bez 7-Zip zainstalowanego na maszynie
testujacej (docs/08_REPO.md §3). ``make verify-sources`` NIE wykonuje ekstrakcji
(09_DECISIONS.md §2.1) — to jest wylacznie praca tego modulu, raz, z wynikiem
cache'owanym w ``data/raw/eqtb/`` i ``data/interim/eqtb_tokens.parquet``.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from src.data.verify_sources import compare_columns, parse_header
from src.paths import CONFIGS_DIR, DATA_INTERIM_DIR, DATA_RAW_DIR
from src.utils.io import ensure_dir, read_yaml
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)

ARCHIVE_URL = "https://raw.githubusercontent.com/NoorBayan/Quranic/main/corpus/Quranic.rar"

RAW_DIR: Path = DATA_RAW_DIR / "eqtb"
RAW_ARCHIVE_PATH: Path = RAW_DIR / "Quranic.rar"
RAW_CSV_PATH: Path = RAW_DIR / "Quranic.csv"
INTERIM_TOKENS_PATH: Path = DATA_INTERIM_DIR / "eqtb_tokens.parquet"

HEADER_PROBE_BYTES = 65535

SEVEN_ZIP_CANDIDATES: tuple[str, ...] = (
    r"C:\Program Files\7-Zip\7z.exe",
    r"C:\Program Files (x86)\7-Zip\7z.exe",
    "7z",
    "7zz",
)


class MissingSevenZipError(RuntimeError):
    """7-Zip nie znalezione. Zaleznosc systemowa udokumentowana w pyproject.toml."""


class EqtbDownloadError(RuntimeError):
    """Archiwum EQTB nieosiagalne, puste po rozpakowaniu, albo naglowek nie
    zgadza sie z mapowaniem znanym z 09_DECISIONS.md §2.1 (AGENTS.md: nie
    zgadujemy danych — blad jest jawny, nie cichy fallback)."""


class ArchiveFetcher(Protocol):
    def __call__(self) -> bytes: ...


class ArchiveExtractor(Protocol):
    def __call__(self, archive_bytes: bytes) -> bytes: ...


@dataclass(frozen=True)
class EqtbDownloadResult:
    tokens_path: Path
    raw_archive_path: Path
    raw_csv_path: Path
    stats: dict[str, Any]
    from_cache: bool


def find_seven_zip() -> str:
    for candidate in SEVEN_ZIP_CANDIDATES:
        if shutil.which(candidate) or Path(candidate).exists():
            return candidate
    raise MissingSevenZipError(
        "7-Zip nie znalezione. Instalacja: winget install --id 7zip.7zip -e "
        "(Linux: apt install p7zip-full; macOS: brew install sevenzip). "
        "Patrz komentarz w pyproject.toml."
    )


def fetch_archive_bytes(url: str = ARCHIVE_URL, *, timeout: int = 60) -> bytes:
    """Domyslny `ArchiveFetcher` — jedyne miejsce w tym module, ktore dotyka sieci."""
    import requests

    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def extract_csv_with_7zip(archive_bytes: bytes, *, seven_zip: str | None = None) -> bytes:
    """Domyslny `ArchiveExtractor` — jedyne miejsce w tym module, ktore wola 7-Zip."""
    seven_zip = seven_zip or find_seven_zip()
    with tempfile.TemporaryDirectory(prefix="eqtb_extract_") as tmp:
        tmp_dir = Path(tmp)
        archive_path = tmp_dir / "Quranic.rar"
        archive_path.write_bytes(archive_bytes)
        subprocess.run(  # noqa: S603
            [seven_zip, "x", str(archive_path), f"-o{tmp_dir}", "-y"],
            check=True,
            capture_output=True,
        )
        extracted = [p for p in tmp_dir.iterdir() if p.is_file() and p.name != archive_path.name]
        if not extracted:
            raise EqtbDownloadError("Archiwum Quranic.rar jest puste po rozpakowaniu.")
        if len(extracted) > 1:
            LOGGER.warning(
                "archiwum Quranic.rar zawiera wiecej niz jeden plik, biore pierwszy",
                extra={"files": [p.name for p in extracted]},
            )
        return extracted[0].read_bytes()


def _eqtb_spec() -> dict[str, Any]:
    specs = read_yaml(CONFIGS_DIR / "sources.yaml")["sources"]
    return next(s for s in specs if s["id"] == "eqtb")


def parse_eqtb_csv_bytes(blob: bytes) -> pd.DataFrame:
    """Parsuje CALY plik ``Quranic.csv`` (nie tylko naglowek).

    Reuzywa sniffowania kodowania/separatora z ``verify_sources.py`` — ta sama
    procedura, ktora sprawdzila ``corpus/Quran.csv`` i sam naglowek ``Quranic.csv``
    w dochodzeniu diagnostycznym (``scripts/probe_eqtb_archive.py``).
    """
    _, encoding, delimiter = parse_header(blob[:HEADER_PROBE_BYTES])
    text = blob.decode(encoding, errors="replace").lstrip("\ufeff")
    n_replacement_chars = text.count("\ufffd")
    if n_replacement_chars:
        LOGGER.warning(
            "znaki zastepcze przy dekodowaniu Quranic.csv — mozliwe uszkodzenie danych",
            extra={"encoding": encoding, "n_replacement_chars": n_replacement_chars},
        )
    df = pd.read_csv(StringIO(text), sep=delimiter, dtype=str, keep_default_na=False)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def canonicalize_columns(
    df: pd.DataFrame,
    *,
    expected_columns: Sequence[str],
    rename: dict[str, str],
    unresolved: Sequence[str],
) -> pd.DataFrame:
    """Mapuje kolumny zrodlowe na kanoniczne z 09_DECISIONS.md §2.1.

    Kolumny z ``unresolved`` (np. ``constituent_node``) dostaja wartosc ``None``,
    jesli nie wystepuja w zrodle pod zadna znana nazwa — to jest jawna decyzja
    (09_DECISIONS.md §2.1: "to pole zostaje nullable/unmapped"), nie przeoczenie.
    """
    renamed = df.rename(columns=rename)
    for col in unresolved:
        if col not in renamed.columns:
            renamed[col] = None
    missing = [c for c in expected_columns if c not in renamed.columns]
    if missing:
        raise EqtbDownloadError(
            "Po zmapowaniu wg configs/sources.yaml wciaz brakuje kolumn oczekiwanych "
            f"w 09_DECISIONS.md §2.1: {missing}. To jest jeden z czterech przypadkow "
            "'zatrzymaj sie i zapytaj' z AGENTS.md — nie zgaduj dalej."
        )
    return renamed[list(expected_columns)]


def compute_corpus_stats(df: pd.DataFrame) -> dict[str, Any]:
    """Liczby o korpusie EQTB — WYLICZONE programowo (AGENTS.md zasada 8).

    Dwie rozne wielkosci, ktore latwo pomylic (i raz pomylono je w tym module —
    patrz DEVIATIONS.md D-06):

    * ``n_tokens`` — liczba slow ortograficznych, ``token_unit: orthographic_word``
      z ``docs/09_DECISIONS.md`` §6. To jest ``distinct (chapter_id, verse_id,
      word_id)``. UWAGA: samego ``verse_id`` NIE wystarczy — resetuje sie co sure
      (max obserwowana wartosc 286 = liczba wersetow Al-Baqary), wiec bez
      ``chapter_id`` wersety z roznych sur zderzalyby sie na tym samym ``word_id``.
    * ``n_segments`` — liczba wierszy tabeli po odfiltrowaniu placeholderow,
      czyli liczba segmentow morfologicznych (jedno slowo ortograficzne moze
      miec kilka segmentow: proklityki, temat, sufiksy — kazdy jako osobny
      wiersz z tym samym ``word_id``).

    Identyfikacja wiersza-placeholdera (wirtualny wezel zaleznosciowy klauzuli,
    nie powierzchniowy token): ``word_id == '0'`` — zweryfikowane na calym
    pliku jako IDENTYCZNY zbior co ``location == '_'`` (11157 z 11157 wierszy
    w obu, XOR = 0). To NIE jest ``rel_label == 'root'``: `rel_label` tych
    wierszy przyjmuje 75 roznych wartosci (Subj, Pred, Adj, circ, root, ...),
    bo koduje relacje CALEJ klauzuli do nadrzedniej struktury, nie tylko
    dosłowny korzen drzewa. Nie zgadywano tego skladniowo — sprawdzono na danych.
    """
    is_placeholder = df["word_id"].astype(str).str.strip() == "0"
    real_tokens = df.loc[~is_placeholder]
    word_key = real_tokens[["chapter_id", "verse_id", "word_id"]].drop_duplicates()
    return {
        "n_raw_rows": int(len(df)),
        "n_root_placeholder_rows": int(is_placeholder.sum()),
        "n_segments": int(len(real_tokens)),
        "n_tokens": int(len(word_key)),
        "n_surahs": int(real_tokens["chapter_id"].nunique()),
        "n_verses": int(real_tokens[["chapter_id", "verse_id"]].drop_duplicates().shape[0]),
    }


def download_and_parse_eqtb(
    *,
    fetch: ArchiveFetcher = fetch_archive_bytes,
    extract: ArchiveExtractor = extract_csv_with_7zip,
    force: bool = False,
    raw_archive_path: Path = RAW_ARCHIVE_PATH,
    raw_csv_path: Path = RAW_CSV_PATH,
    tokens_path: Path = INTERIM_TOKENS_PATH,
) -> EqtbDownloadResult:
    """Orkiestrator T-009: cache -> pobranie -> ekstrakcja -> parsowanie -> zapis.

    Idempotentny: jesli ``data/raw/eqtb/Quranic.csv`` juz istnieje i ``force=False``,
    nic nie pobiera i nie rozpakowuje ponownie.
    """
    spec = _eqtb_spec()

    from_cache = raw_csv_path.exists() and not force
    if from_cache:
        csv_bytes = raw_csv_path.read_bytes()
    else:
        if raw_archive_path.exists() and not force:
            archive_bytes = raw_archive_path.read_bytes()
        else:
            LOGGER.info("pobieram archiwum EQTB", extra={"url": ARCHIVE_URL})
            archive_bytes = fetch()
            ensure_dir(raw_archive_path.parent)
            raw_archive_path.write_bytes(archive_bytes)
        csv_bytes = extract(archive_bytes)
        ensure_dir(raw_csv_path.parent)
        raw_csv_path.write_bytes(csv_bytes)

    df_raw = parse_eqtb_csv_bytes(csv_bytes)

    expected_columns: list[str] = spec["expected_columns"]
    rename: dict[str, str] = spec.get("column_rename", {})
    unresolved: list[str] = spec.get("unresolved_columns", [])

    missing, extra = compare_columns(list(df_raw.columns), expected_columns)
    still_missing = sorted(set(missing) - set(rename.values()) - set(unresolved))
    if still_missing:
        raise EqtbDownloadError(
            "Naglowek Quranic.csv nie zawiera kolumn spoza znanego mapowania "
            f"09_DECISIONS.md §2.1: {still_missing}. Format zrodla sie zmienil — "
            "zatrzymaj sie i zapytaj (AGENTS.md), nie zgaduj nowego mapowania."
        )

    df = canonicalize_columns(
        df_raw, expected_columns=expected_columns, rename=rename, unresolved=unresolved
    )

    ensure_dir(tokens_path.parent)
    df.to_parquet(tokens_path, index=False)

    stats = compute_corpus_stats(df)
    stats["extra_columns_dropped"] = extra
    stats["unresolved_columns"] = list(unresolved)
    stats["column_rename_applied"] = rename
    stats["pipeline_input_column"] = spec.get("pipeline_input_column")

    return EqtbDownloadResult(
        tokens_path=tokens_path,
        raw_archive_path=raw_archive_path,
        raw_csv_path=raw_csv_path,
        stats=stats,
        from_cache=from_cache,
    )
