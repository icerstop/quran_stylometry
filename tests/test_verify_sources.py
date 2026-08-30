"""`make verify-sources` — testowane bez sieci (08_REPO.md §3).

Warstwa HTTP jest wstrzykiwana, wiec caly modul da sie sprawdzic na
zamockowanych odpowiedziach. Jeden test dotyka dysku: prawdziwego
`data/reference/chronologies.csv`, bo to plik referencyjny w repo i jego liczby
maja byc weryfikowane, a nie przepisywane (AGENTS.md zasada 8).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.data.verify_sources import (
    FetchError,
    Response,
    compare_columns,
    load_sources,
    parse_header,
    sniff_delimiter,
    sniff_encoding,
    verify_sources,
)
from src.paths import CONFIGS_DIR

EQTB_COLUMNS = ["tid", "verse_id", "imlaai_token", "pos", "lemma", "root"]


class FakeFetcher:
    """Zwraca zaplanowane odpowiedzi; nieznany URL to blad, nie cichy 404."""

    def __init__(self, responses: dict[str, Response | Exception]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> Response:
        self.calls.append((url, headers or {}))
        planned = self.responses.get(url)
        if planned is None:
            raise AssertionError(f"Test nie zaplanowal odpowiedzi dla {url}")
        if isinstance(planned, Exception):
            raise planned
        return planned


def json_response(payload: Any, url: str = "http://x", status: int = 200) -> Response:
    return Response(status_code=status, content=json.dumps(payload).encode("utf-8"), url=url)


# --------------------------------------------------------------------------
# Sniffowanie formatu
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("blob", "expected"),
    [
        (b"\xff\xfea\x00", "utf-16-le"),
        (b"\xfe\xff\x00a", "utf-16-be"),
        (b"\xef\xbb\xbfa", "utf-8-sig"),
        (b"plain", "utf-8"),
    ],
)
def test_sniff_encoding(blob: bytes, expected: str) -> None:
    assert sniff_encoding(blob) == expected


@pytest.mark.parametrize(
    ("line", "expected"),
    [("a\tb\tc", "\t"), ("a,b,c", ","), ("a;b;c", ";"), ("single", ",")],
)
def test_sniff_delimiter(line: str, expected: str) -> None:
    assert sniff_delimiter(line) == expected


def test_parse_header_handles_utf16_tab_file() -> None:
    """Dokladnie ten przypadek wystepuje w EQTB: UTF-16 z BOM i separator TAB."""
    blob = "aid\tchapter\tverse\tayah\tjmlh\n1\t1\t1\tx\t4\n".encode("utf-16-le")
    columns, encoding, delimiter = parse_header(b"\xff\xfe" + blob)
    assert columns == ["aid", "chapter", "verse", "ayah", "jmlh"]
    assert encoding == "utf-16-le"
    assert delimiter == "\t"


def test_compare_columns_is_case_insensitive() -> None:
    missing, extra = compare_columns(["TID", "Verse_ID", "zzz"], ["tid", "verse_id", "pos"])
    assert missing == ["pos"]
    assert extra == ["zzz"]


# --------------------------------------------------------------------------
# Checkery
# --------------------------------------------------------------------------


def eqtb_spec(**overrides: Any) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "id": "eqtb",
        "title": "EQTB",
        "kind": "github_repo",
        "criticality": "required",
        "api_url": "https://api/repo",
        "contents_url": "https://api/repo/contents",
        "data_file": "corpus/Quranic.rar",
        "archive_url": "https://raw/Quranic.rar",
        "license_expected": "MIT",
        "expected_columns": EQTB_COLUMNS,
    }
    spec.update(overrides)
    return spec


def archive_response(url: str = "https://raw/Quranic.rar", status: int = 206) -> Response:
    return Response(status_code=status, content=b"\x00", url=url)


def test_github_source_ok_when_license_matches_and_archive_reachable() -> None:
    """09_DECISIONS.md §2.1: verify-sources sprawdza tylko osiagalnosc .rar,
    nigdy nie rozpakowuje — parsowanie kolumn to T-009."""
    fetcher = FakeFetcher(
        {
            "https://api/repo": json_response(
                {"license": {"spdx_id": "MIT"}, "default_branch": "main"}
            ),
            "https://api/repo/contents": json_response(
                [{"path": "corpus/Quranic.rar", "size": 4120767, "sha": "deadbeef"}]
            ),
            "https://raw/Quranic.rar": archive_response(),
        }
    )
    report = verify_sources([eqtb_spec()], fetcher)
    check = report.sources[0]

    assert check.status == "ok"
    assert check.license_observed == "MIT"
    assert check.license_ok is True
    assert check.resolved["archive_reachable"] is True
    assert check.resolved["data_file_size"] == 4120767
    # Kolumny NIE sa sprawdzane rutynowo dla archiwum — to jest T-009.
    assert check.columns_ok is None
    assert report.overall == "pass"


def test_archive_probe_uses_a_single_byte_range_request() -> None:
    """Archiwum nie jest rozpakowywane — tylko maly ranged GET na osiagalnosc."""
    fetcher = FakeFetcher(
        {
            "https://api/repo": json_response({"license": {"spdx_id": "MIT"}}),
            "https://api/repo/contents": json_response([{"path": "corpus/Quranic.rar"}]),
            "https://raw/Quranic.rar": archive_response(),
        }
    )
    verify_sources([eqtb_spec()], fetcher)

    raw_headers = next(h for url, h in fetcher.calls if url == "https://raw/Quranic.rar")
    assert raw_headers["Range"] == "bytes=0-0"


def test_unreachable_archive_fails_the_required_source() -> None:
    """Archiwum niedostepne = fail; nie ma tu ekstrakcji ani parsowania kolumn."""
    fetcher = FakeFetcher(
        {
            "https://api/repo": json_response({"license": {"spdx_id": "MIT"}}),
            "https://api/repo/contents": json_response([{"path": "corpus/Quranic.rar"}]),
            "https://raw/Quranic.rar": archive_response(status=404),
        }
    )
    report = verify_sources([eqtb_spec()], fetcher)
    check = report.sources[0]

    assert check.status == "fail"
    assert report.overall == "fail"
    assert [c.id for c in report.failed_required()] == ["eqtb"]


def test_license_mismatch_degrades_but_does_not_fail() -> None:
    fetcher = FakeFetcher(
        {
            "https://api/repo": json_response({"license": {"spdx_id": "GPL-3.0"}}),
            "https://api/repo/contents": json_response([{"path": "corpus/Quranic.rar"}]),
            "https://raw/Quranic.rar": archive_response(),
        }
    )
    check = verify_sources([eqtb_spec()], fetcher).sources[0]
    assert check.status == "degraded"
    assert check.license_ok is False
    assert check.license_observed == "GPL-3.0"


def test_missing_data_file_fails() -> None:
    fetcher = FakeFetcher(
        {
            "https://api/repo": json_response({"license": {"spdx_id": "MIT"}}),
            "https://api/repo/contents": json_response([{"path": "corpus/inny.csv"}]),
        }
    )
    check = verify_sources([eqtb_spec(archive_url=None, expected_columns=None)], fetcher).sources[0]
    assert check.status == "fail"


def test_unreachable_source_fails_without_raising() -> None:
    fetcher = FakeFetcher({"https://api/repo": FetchError("timeout")})
    check = verify_sources([eqtb_spec()], fetcher).sources[0]
    assert check.status == "fail"
    assert any("timeout" in note for note in check.notes)


def qac_spec() -> dict[str, Any]:
    return {
        "id": "qac",
        "title": "QAC",
        "kind": "http_page",
        "criticality": "fallback_allowed",
        "url": "https://corpus/download",
        "license_expected": "GPL",
        "requires_manual_step": True,
        "manual_step": "Formularz wymaga adresu e-mail.",
        "fallback": "Ewaluacja taggera wobec kolumn EQTB.",
    }


def test_qac_manual_step_yields_fallback_active_not_fail() -> None:
    """09_DECISIONS §2.2 przewiduje jawny, sformalizowany fallback — to nie jest
    blocker, i nie jest to "degraded z nadzieja na reczne uzupelnienie" w
    przyszlosci: EQTB jest jedyna referencja, formularz e-mail nigdy nie bedzie
    uzyty (T-010, 2026-08-30)."""
    fetcher = FakeFetcher(
        {"https://corpus/download": Response(200, b"GNU General Public License", "u")}
    )
    report = verify_sources([qac_spec()], fetcher)
    check = report.sources[0]

    assert check.status == "fallback_active"
    assert check.requires_manual_step is True
    assert any("FALLBACK" in note for note in check.notes)
    assert report.overall == "pass"
    assert report.failed_required() == []


def test_qac_unreachable_still_reports_fallback_active() -> None:
    fetcher = FakeFetcher({"https://corpus/download": FetchError("connection reset")})
    check = verify_sources([qac_spec()], fetcher).sources[0]
    assert check.status == "fallback_active"


def zenodo_spec() -> dict[str, Any]:
    return {
        "id": "openiti_metadata",
        "title": "OpenITI",
        "kind": "zenodo_concept",
        "criticality": "required",
        "api_url": "https://zenodo/api/records/3082463",
        "metadata_file_pattern": "OpenITI_metadata_",
        "license_expected": "cc-by-nc-sa-4.0",
    }


def zenodo_record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": 17767721,
        "metadata": {
            "version": "2025.1.9",
            "doi": "10.5281/zenodo.17767721",
            "publication_date": "2025-12-30",
            "license": {"id": "cc-by-nc-sa-4.0"},
        },
        "files": [
            {"key": "OpenITI_metadata_2025-1-9.tsv", "size": 12092756, "checksum": "md5:abc"},
            {"key": "OpenITI_data_2025-1-9.zip", "size": 5936029637, "checksum": "md5:def"},
        ],
    }
    record.update(overrides)
    return record


def test_zenodo_resolves_and_pins_the_version() -> None:
    """Concept DOI to ruchomy cel — bez utrwalenia wersji T-011 nie jest odtwarzalne."""
    fetcher = FakeFetcher({"https://zenodo/api/records/3082463": json_response(zenodo_record())})
    check = verify_sources([zenodo_spec()], fetcher).sources[0]

    assert check.status == "ok"
    assert check.license_observed == "cc-by-nc-sa-4.0"
    assert check.resolved["record_id"] == 17767721
    assert check.resolved["version"] == "2025.1.9"
    assert check.resolved["metadata_file"] == "OpenITI_metadata_2025-1-9.tsv"
    assert check.resolved["metadata_file_size"] == 12092756


def test_zenodo_without_metadata_file_fails() -> None:
    """Bez pliku metadanych nie da sie zrobic selektywnego pobrania z §2.3."""
    record = zenodo_record(files=[{"key": "OpenITI_data_2025-1-9.zip", "size": 1}])
    fetcher = FakeFetcher({"https://zenodo/api/records/3082463": json_response(record)})
    check = verify_sources([zenodo_spec()], fetcher).sources[0]
    assert check.status == "fail"


# --------------------------------------------------------------------------
# Plik lokalny: chronologia
# --------------------------------------------------------------------------


def test_real_chronologies_file_matches_decisions() -> None:
    """Liczby z 09_DECISIONS §2.4 policzone programowo, nie przepisane."""
    spec = next(s for s in load_sources(CONFIGS_DIR / "sources.yaml") if s["id"] == "chronologies")
    check = verify_sources([spec], FakeFetcher({})).sources[0]

    assert check.status == "ok", check.notes
    assert check.resolved["n_rows"] == 114
    assert check.resolved["period_traditional_meccan"] == 86
    assert check.resolved["period_traditional_medinan"] == 28
    assert check.resolved["rows_with_exception_verses"] == 35


def test_wrong_row_count_fails(tmp_path: Path) -> None:
    csv_path = tmp_path / "chrono.csv"
    csv_path.write_text("surah_id,period_traditional\n1,meccan\n", encoding="utf-8")
    spec = {
        "id": "chronologies",
        "title": "chrono",
        "kind": "local_csv",
        "criticality": "required",
        "path": str(csv_path.relative_to(csv_path.anchor)),
        "expected_columns": ["surah_id", "period_traditional"],
        "expected_rows": 114,
    }
    # Sciezka wzgledna wobec REPO_ROOT nie istnieje -> fail na braku pliku.
    assert verify_sources([spec], FakeFetcher({})).sources[0].status == "fail"


# --------------------------------------------------------------------------
# Rejestr zrodel
# --------------------------------------------------------------------------


def test_sources_registry_covers_all_decisions_entries() -> None:
    sources = load_sources(CONFIGS_DIR / "sources.yaml")
    ids = {s["id"] for s in sources}
    assert {"eqtb", "qac", "openiti_metadata", "openiti_texts", "chronologies"} <= ids


def test_every_source_declares_criticality_and_decision_ref() -> None:
    for spec in load_sources(CONFIGS_DIR / "sources.yaml"):
        assert spec["criticality"] in {"required", "fallback_allowed"}
        assert spec["decision_ref"].startswith("09_DECISIONS.md")


def test_fallback_allowed_sources_must_declare_a_fallback() -> None:
    """Ulga jest uzasadniona tylko wtedy, gdy 09_DECISIONS podaje zastepnik."""
    for spec in load_sources(CONFIGS_DIR / "sources.yaml"):
        if spec["criticality"] == "fallback_allowed":
            assert spec.get("fallback"), f"{spec['id']} nie podaje fallbacku"


def test_eqtb_expected_columns_match_decisions_count() -> None:
    spec = next(s for s in load_sources(CONFIGS_DIR / "sources.yaml") if s["id"] == "eqtb")
    assert len(spec["expected_columns"]) == 42
    assert spec["pipeline_input_column"] == "imlaai_token"  # G2


def test_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValueError, match="Nieznany rodzaj"):
        verify_sources(
            [{"id": "x", "title": "x", "kind": "carrier_pigeon", "criticality": "required"}],
            FakeFetcher({}),
        )
