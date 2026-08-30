"""Weryfikacja zrodel z docs/09_DECISIONS.md §2 (`make verify-sources`).

Sprawdza trzy rzeczy dla kazdego zrodla: osiagalnosc (HTTP 200), oczekiwane
kolumny/pliki i licencje. Raport ladauje w `results/source_check.json`.

Zasady, ktore ksztaltuja ten modul:

* Kod nie zna zadnego URL-a — wszystko pochodzi z `configs/sources.yaml`.
* Licencja jest ODCZYTYWANA ze zrodla i porownywana z oczekiwaniem, nie
  przepisywana z dokumentacji (AGENTS.md zasada 8).
* Zrodlo z `criticality: fallback_allowed` nie moze wywrocic pipeline'u, jesli
  09_DECISIONS przewiduje dla niego jawny fallback (dotyczy QAC, §2.2).
* Warstwa sieciowa jest wstrzykiwana (`Fetcher`), zeby testy chodzily bez sieci
  (08_REPO.md §3).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from src.paths import REPO_ROOT
from src.utils.io import read_yaml
from src.utils.logging import get_logger
from src.utils.provenance import utc_now_iso

LOGGER = get_logger(__name__)

Status = Literal["ok", "degraded", "fail"]
Overall = Literal["pass", "degraded", "fail"]

HEADER_PROBE_BYTES = 65535
_TIMEOUT_S = 30


class FetchError(RuntimeError):
    """Zrodlo nieosiagalne. Jeden z czterech przypadkow 'zatrzymaj sie i zapytaj'."""


@dataclass(frozen=True)
class Response:
    status_code: int
    content: bytes
    url: str

    def json(self) -> Any:
        import json

        return json.loads(self.content.decode("utf-8"))

    @property
    def ok(self) -> bool:
        # 206 Partial Content jest poprawna odpowiedzia na zapytanie zakresowe.
        return self.status_code in (200, 206)


class Fetcher(Protocol):
    """Minimalny kontrakt warstwy sieciowej — pozwala testowac bez sieci."""

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> Response: ...


class RequestsFetcher:
    """Domyslna implementacja oparta na `requests`."""

    def __init__(self, timeout: int = _TIMEOUT_S) -> None:
        self._timeout = timeout

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> Response:
        import requests

        try:
            resp = requests.get(url, headers=headers or {}, timeout=self._timeout)
        except requests.RequestException as exc:
            raise FetchError(f"{url}: {exc}") from exc
        return Response(status_code=resp.status_code, content=resp.content, url=url)


class SourceCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    role: str = ""
    decision_ref: str = ""
    criticality: Literal["required", "fallback_allowed"]
    kind: str
    status: Status
    url: str | None = None
    http_status: int | None = None
    license_expected: str | None = None
    license_observed: str | None = None
    license_ok: bool | None = None
    columns_ok: bool | None = None
    columns_missing: list[str] = Field(default_factory=list)
    columns_extra: list[str] = Field(default_factory=list)
    requires_manual_step: bool = False
    resolved: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class SourceCheckReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall: Overall
    checked_at: str
    decisions_ref: str = "docs/09_DECISIONS.md §2"
    sources: list[SourceCheck]

    def failed_required(self) -> list[SourceCheck]:
        return [s for s in self.sources if s.criticality == "required" and s.status == "fail"]


# --------------------------------------------------------------------------
# Pomocnicze: sniffowanie kodowania i separatora
# --------------------------------------------------------------------------

_BOMS: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
)


def sniff_encoding(blob: bytes) -> str:
    """Rozpoznaje kodowanie po BOM.

    Nie jest to nadgorliwosc: `corpus/pos.csv` w repo EQTB jest zapisany w UTF-16
    z BOM-em, mimo rozszerzenia `.csv`. Odczyt jako UTF-8 daje tam smieci, ktore
    wygladaja jak brak oczekiwanych kolumn.
    """
    for bom, encoding in _BOMS:
        if blob.startswith(bom):
            return encoding
    return "utf-8"


def sniff_delimiter(header_line: str) -> str:
    """Wybiera separator po liczbie wystapien w wierszu naglowka."""
    candidates = {
        "\t": header_line.count("\t"),
        ",": header_line.count(","),
        ";": header_line.count(";"),
    }
    best, count = max(candidates.items(), key=lambda item: item[1])
    return best if count > 0 else ","


def parse_header(blob: bytes) -> tuple[list[str], str, str]:
    """Zwraca (kolumny, kodowanie, separator) z pierwszego wiersza."""
    encoding = sniff_encoding(blob)
    text = blob.decode(encoding, errors="replace").lstrip("\ufeff")
    first_line = text.splitlines()[0] if text.splitlines() else ""
    delimiter = sniff_delimiter(first_line)
    columns = [col.strip().strip('"').lstrip("\ufeff") for col in first_line.split(delimiter)]
    return [c for c in columns if c], encoding, delimiter


def compare_columns(
    observed: Sequence[str], expected: Sequence[str]
) -> tuple[list[str], list[str]]:
    observed_set = {c.lower() for c in observed}
    expected_set = {c.lower() for c in expected}
    return sorted(expected_set - observed_set), sorted(observed_set - expected_set)


# --------------------------------------------------------------------------
# Checkery per rodzaj zrodla
# --------------------------------------------------------------------------


def _base_check(spec: dict[str, Any], status: Status) -> dict[str, Any]:
    return {
        "id": spec["id"],
        "title": spec.get("title", spec["id"]),
        "role": spec.get("role", ""),
        "decision_ref": spec.get("decision_ref", ""),
        "criticality": spec.get("criticality", "required"),
        "kind": spec["kind"],
        "status": status,
        "license_expected": spec.get("license_expected"),
        "notes": list(spec.get("notes", [])),
    }


def check_github_repo(spec: dict[str, Any], fetcher: Fetcher) -> SourceCheck:
    payload = _base_check(spec, "ok")
    payload["url"] = spec["api_url"]

    try:
        resp = fetcher.get(spec["api_url"], headers={"Accept": "application/vnd.github+json"})
    except FetchError as exc:
        payload.update(status="fail", notes=[*payload["notes"], f"Nieosiagalne: {exc}"])
        return SourceCheck(**payload)

    payload["http_status"] = resp.status_code
    if not resp.ok:
        payload["status"] = "fail"
        payload["notes"].append(f"HTTP {resp.status_code} na API repozytorium.")
        return SourceCheck(**payload)

    meta = resp.json()
    observed_license = (meta.get("license") or {}).get("spdx_id")
    payload["license_observed"] = observed_license
    expected = spec.get("license_expected")
    if expected is not None:
        payload["license_ok"] = (observed_license or "").upper() == str(expected).upper()
        if not payload["license_ok"]:
            payload["status"] = "degraded"
            payload["notes"].append(
                f"Licencja zaobserwowana '{observed_license}' != oczekiwana '{expected}'."
            )
    payload["resolved"] = {
        "default_branch": meta.get("default_branch"),
        "pushed_at": meta.get("pushed_at"),
        "archived": meta.get("archived"),
    }

    if spec.get("contents_url"):
        payload = _check_repo_contents(spec, fetcher, payload)
    if spec.get("archive_url"):
        # 09_DECISIONS.md §2.1: archiwum sprawdzamy tylko na osiagalnosc,
        # nigdy nie rozpakowujemy przy rutynowym `make verify-sources`.
        payload = _check_archive_reachable(spec, fetcher, payload)
    elif spec.get("raw_url") and spec.get("expected_columns"):
        payload = _check_remote_header(spec, fetcher, payload)

    return SourceCheck(**payload)


def _check_repo_contents(
    spec: dict[str, Any], fetcher: Fetcher, payload: dict[str, Any]
) -> dict[str, Any]:
    try:
        resp = fetcher.get(spec["contents_url"], headers={"Accept": "application/vnd.github+json"})
    except FetchError as exc:
        payload["status"] = "fail"
        payload["notes"].append(f"Katalog danych nieosiagalny: {exc}")
        return payload

    if not resp.ok:
        payload["status"] = "fail"
        payload["notes"].append(f"HTTP {resp.status_code} na katalogu danych.")
        return payload

    entries = resp.json()
    names = [entry.get("path") for entry in entries if isinstance(entry, dict)]
    payload["resolved"]["corpus_files"] = names

    wanted = spec.get("data_file")
    if wanted and wanted not in names:
        payload["status"] = "fail"
        payload["notes"].append(f"Brak oczekiwanego pliku '{wanted}' w katalogu danych.")
    else:
        for entry in entries:
            if isinstance(entry, dict) and entry.get("path") == wanted:
                payload["resolved"]["data_file_size"] = entry.get("size")
                payload["resolved"]["data_file_sha"] = entry.get("sha")
    return payload


def _check_archive_reachable(
    spec: dict[str, Any], fetcher: Fetcher, payload: dict[str, Any]
) -> dict[str, Any]:
    """Sprawdza WYLACZNIE osiagalnosc archiwum (maly ranged GET), bez ekstrakcji.

    `corpus/Quranic.rar` jest binarny — nie da sie z niego sparsowac naglowka
    kolumn bez rozpakowania. 09_DECISIONS.md §2.1 wprost zabrania rozpakowywania
    przy rutynowym `verify-sources`: pelna ekstrakcja i parsowanie to praca
    T-009 (`src/data/download_eqtb.py`), wykonana raz, z wynikiem cache'owanym.
    """
    url = spec["archive_url"]
    try:
        resp = fetcher.get(url, headers={"Range": "bytes=0-0"})
    except FetchError as exc:
        payload["status"] = "fail"
        payload["notes"].append(f"Archiwum '{url}' nieosiagalne: {exc}")
        return payload

    if not resp.ok:
        payload["status"] = "fail"
        payload["notes"].append(f"HTTP {resp.status_code} na archiwum '{url}'.")
        return payload

    payload["resolved"]["archive_url"] = url
    payload["resolved"]["archive_reachable"] = True
    payload["resolved"]["archive_range_probe_status"] = resp.status_code
    payload["notes"].append(
        "Archiwum sprawdzone tylko na osiagalnosc (bez ekstrakcji). "
        "Pelne rozpakowanie + parsowanie kolumn: T-009 (src/data/download_eqtb.py)."
    )
    return payload


def _check_remote_header(
    spec: dict[str, Any], fetcher: Fetcher, payload: dict[str, Any]
) -> dict[str, Any]:
    """Pobiera tylko poczatek pliku (Range) i porownuje naglowek z oczekiwaniem.

    Zapytanie zakresowe jest tu istotne: `corpus/Quran.csv` ma ponad 5 MB,
    a do sprawdzenia kontraktu wystarczy pierwszy wiersz.
    """
    try:
        resp = fetcher.get(spec["raw_url"], headers={"Range": f"bytes=0-{HEADER_PROBE_BYTES}"})
    except FetchError as exc:
        payload["status"] = "fail"
        payload["notes"].append(f"Plik danych nieosiagalny: {exc}")
        return payload

    if not resp.ok:
        payload["status"] = "fail"
        payload["notes"].append(f"HTTP {resp.status_code} na pliku danych.")
        return payload

    columns, encoding, delimiter = parse_header(resp.content)
    missing, extra = compare_columns(columns, spec["expected_columns"])

    payload["columns_missing"] = missing
    payload["columns_extra"] = extra
    payload["columns_ok"] = not missing
    payload["resolved"].update(
        {
            "observed_encoding": encoding,
            "observed_delimiter": {"\t": "tab", ",": "comma", ";": "semicolon"}.get(
                delimiter, delimiter
            ),
            "observed_columns": columns,
            "n_observed_columns": len(columns),
            "n_expected_columns": len(spec["expected_columns"]),
        }
    )

    if missing:
        # AGENTS.md: rozbieznosc formatu wobec 09_DECISIONS §2 to jeden z czterech
        # przypadkow, w ktorych agent ma sie zatrzymac i zapytac, a nie zgadywac.
        payload["status"] = "fail"
        payload["notes"].append(
            f"Naglowek nie zawiera {len(missing)} oczekiwanych kolumn z 09_DECISIONS §2.1: "
            + ", ".join(missing)
        )
    elif extra:
        payload["notes"].append(f"Kolumny nadmiarowe (nieblokujace): {', '.join(extra)}")
    return payload


def check_http_page(spec: dict[str, Any], fetcher: Fetcher) -> SourceCheck:
    payload = _base_check(spec, "ok")
    payload["url"] = spec["url"]
    payload["requires_manual_step"] = bool(spec.get("requires_manual_step"))

    try:
        resp = fetcher.get(spec["url"])
    except FetchError as exc:
        payload["status"] = "fail"
        payload["notes"].append(f"Nieosiagalne: {exc}")
        return _apply_fallback(spec, SourceCheck(**payload))

    payload["http_status"] = resp.status_code
    if not resp.ok:
        payload["status"] = "fail"
        payload["notes"].append(f"HTTP {resp.status_code}.")
        return _apply_fallback(spec, SourceCheck(**payload))

    body = resp.content.decode("utf-8", errors="replace")
    expected = spec.get("license_expected")
    if expected:
        found = str(expected).lower() in body.lower() or "general public license" in body.lower()
        payload["license_observed"] = str(expected) if found else None
        payload["license_ok"] = found
        if not found:
            payload["notes"].append(
                f"Na stronie nie znaleziono potwierdzenia licencji '{expected}'."
            )

    if payload["requires_manual_step"]:
        # Strona odpowiada, ale pobranie wymaga formularza. Nie obchodzimy tego
        # (AGENTS.md zasada 9), wiec zrodlo jest `degraded`, a nie `ok`.
        payload["status"] = "degraded"
        payload["notes"].append(spec.get("manual_step", "Pobranie wymaga kroku recznego."))
    return _apply_fallback(spec, SourceCheck(**payload))


def check_zenodo_concept(spec: dict[str, Any], fetcher: Fetcher) -> SourceCheck:
    payload = _base_check(spec, "ok")
    payload["url"] = spec["api_url"]

    try:
        resp = fetcher.get(spec["api_url"])
    except FetchError as exc:
        payload["status"] = "fail"
        payload["notes"].append(f"Nieosiagalne: {exc}")
        return SourceCheck(**payload)

    payload["http_status"] = resp.status_code
    if not resp.ok:
        payload["status"] = "fail"
        payload["notes"].append(f"HTTP {resp.status_code} na API Zenodo.")
        return SourceCheck(**payload)

    record = resp.json()
    meta = record.get("metadata", {})
    payload["license_observed"] = (meta.get("license") or {}).get("id")
    expected = spec.get("license_expected")
    if expected is not None:
        payload["license_ok"] = str(payload["license_observed"]).lower() == str(expected).lower()
        if not payload["license_ok"]:
            payload["status"] = "degraded"
            observed = payload["license_observed"]
            payload["notes"].append(
                f"Licencja zaobserwowana '{observed}' != oczekiwana '{expected}'."
            )

    # Concept DOI wskazuje ruchomy cel. Utrwalamy rozwiazana wersje, inaczej
    # selekcja CTRL (T-011) przestaje byc odtwarzalna.
    files = record.get("files", []) or []
    pattern = spec.get("metadata_file_pattern", "")
    metadata_file = next((f for f in files if pattern and pattern in str(f.get("key", ""))), None)

    payload["resolved"] = {
        "record_id": record.get("id"),
        "version": meta.get("version"),
        "version_doi": meta.get("doi"),
        "publication_date": meta.get("publication_date"),
        "metadata_file": (metadata_file or {}).get("key"),
        "metadata_file_size": (metadata_file or {}).get("size"),
        "metadata_file_checksum": (metadata_file or {}).get("checksum"),
        "n_files": len(files),
    }

    if metadata_file is None:
        payload["status"] = "fail"
        payload["notes"].append(
            f"W rekordzie nie ma pliku metadanych pasujacego do '{pattern}'. "
            "Bez niego nie da sie zrobic selektywnego pobrania z §2.3."
        )
    return SourceCheck(**payload)


def check_local_csv(spec: dict[str, Any], _fetcher: Fetcher) -> SourceCheck:
    payload = _base_check(spec, "ok")
    path = REPO_ROOT / spec["path"]
    payload["url"] = spec["path"]

    if not path.exists():
        payload["status"] = "fail"
        payload["notes"].append(f"Brak pliku {spec['path']}.")
        return SourceCheck(**payload)

    blob = path.read_bytes()
    encoding = sniff_encoding(blob)
    with io.StringIO(blob.decode(encoding, errors="replace").lstrip("\ufeff")) as handle:
        rows = list(csv.DictReader(handle))

    columns = list(rows[0].keys()) if rows else []
    missing, extra = compare_columns(columns, spec.get("expected_columns", []))
    payload["columns_missing"] = missing
    payload["columns_extra"] = extra
    payload["columns_ok"] = not missing
    payload["license_observed"] = spec.get("license_expected")
    payload["license_ok"] = True

    counts = _chronology_counts(rows)
    payload["resolved"] = {
        "n_rows": len(rows),
        "observed_encoding": encoding,
        "observed_columns": columns,
        **counts,
    }

    if missing:
        payload["status"] = "fail"
        payload["notes"].append("Brakujace kolumny: " + ", ".join(missing))

    # Liczby z 09_DECISIONS §2.4 sa WERYFIKOWANE, nie przepisywane (AGENTS.md zasada 8).
    expected_rows = spec.get("expected_rows")
    if expected_rows is not None and len(rows) != expected_rows:
        payload["status"] = "fail"
        payload["notes"].append(f"Oczekiwano {expected_rows} wierszy, jest {len(rows)}.")

    for key, expected_value in (spec.get("expected_counts") or {}).items():
        observed = counts.get(key)
        if observed != expected_value:
            payload["status"] = "fail"
            payload["notes"].append(
                f"Niezgodnosc '{key}': oczekiwano {expected_value}, policzono {observed}."
            )
    return SourceCheck(**payload)


def _chronology_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "period_traditional_meccan": sum(
            1 for r in rows if (r.get("period_traditional") or "").strip().lower() == "meccan"
        ),
        "period_traditional_medinan": sum(
            1 for r in rows if (r.get("period_traditional") or "").strip().lower() == "medinan"
        ),
        "rows_with_exception_verses": sum(
            1 for r in rows if (r.get("exception_verses") or "").strip()
        ),
    }


def _apply_fallback(spec: dict[str, Any], check: SourceCheck) -> SourceCheck:
    """Zrodlo z jawnym fallbackiem w 09_DECISIONS nie moze byc `fail`."""
    if (
        check.status == "fail"
        and spec.get("criticality") == "fallback_allowed"
        and spec.get("fallback")
    ):
        return check.model_copy(
            update={
                "status": "degraded",
                "notes": [*check.notes, "FALLBACK: " + " ".join(str(spec["fallback"]).split())],
            }
        )
    if check.status == "degraded" and spec.get("fallback"):
        return check.model_copy(
            update={"notes": [*check.notes, "FALLBACK: " + " ".join(str(spec["fallback"]).split())]}
        )
    return check


_CHECKERS = {
    "github_repo": check_github_repo,
    "http_page": check_http_page,
    "zenodo_concept": check_zenodo_concept,
    "local_csv": check_local_csv,
}


def load_sources(path: Path) -> list[dict[str, Any]]:
    payload = read_yaml(path)
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError(f"{path} nie zawiera niepustej listy `sources`")
    return sources


def verify_sources(sources: list[dict[str, Any]], fetcher: Fetcher) -> SourceCheckReport:
    checks: list[SourceCheck] = []
    for spec in sources:
        checker = _CHECKERS.get(spec["kind"])
        if checker is None:
            raise ValueError(f"Nieznany rodzaj zrodla: {spec['kind']!r}")
        check = checker(spec, fetcher)
        LOGGER.info(
            "sprawdzono zrodlo",
            extra={"source_id": check.id, "status": check.status, "kind": check.kind},
        )
        checks.append(check)

    if any(c.status == "fail" and c.criticality == "required" for c in checks):
        overall: Overall = "fail"
    elif any(c.status in ("degraded", "fail") for c in checks):
        overall = "degraded"
    else:
        overall = "pass"

    return SourceCheckReport(overall=overall, checked_at=utc_now_iso(), sources=checks)
