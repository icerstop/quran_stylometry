"""T-010 — fallback QAC bez pobierania (08_REPO.md §3: bez sieci)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.data.download_qac import (
    QAC_JAVA_API_N_TOKENS,
    QAC_JAVA_API_TOKEN_COUNTS,
    QacDownloadForbiddenError,
    formalize_qac_fallback,
)


def test_qac_java_api_table_has_114_chapters_summing_to_77429() -> None:
    """Zrodlo pierwotne: corpus.quran.com/java/example/tokencountexample.jsp."""
    assert len(QAC_JAVA_API_TOKEN_COUNTS) == 114
    assert set(QAC_JAVA_API_TOKEN_COUNTS) == set(range(1, 115))
    assert QAC_JAVA_API_N_TOKENS == 77_429
    assert QAC_JAVA_API_TOKEN_COUNTS[1] == 29  # Al-Fatiha


def test_formalize_qac_fallback_writes_artifact_without_creating_raw_qac(
    tmp_path: Path,
) -> None:
    eqtb = tmp_path / "eqtb_tokens.parquet"
    eqtb.write_bytes(b"placeholder")
    artifact = tmp_path / "qac_fallback.json"

    result = formalize_qac_fallback(eqtb_tokens_path=eqtb, artifact_path=artifact)

    assert result.payload["status"] == "fallback_active"
    assert result.payload["qac_downloaded"] is False
    assert result.payload["download_attempted"] is False
    assert result.payload["reference_corpus"] == "eqtb"
    assert result.payload["reference_available"] is True
    assert artifact.exists()
    assert not (tmp_path / "qac").exists()


def test_formalize_qac_fallback_records_missing_eqtb_without_failing(
    tmp_path: Path,
) -> None:
    """T-010 nie pobiera EQTB — tylko odnotowuje, czy T-009 juz zrobil swoje."""
    result = formalize_qac_fallback(
        eqtb_tokens_path=tmp_path / "brak.parquet",
        artifact_path=tmp_path / "qac_fallback.json",
    )
    assert result.payload["reference_available"] is False
    assert result.payload["status"] == "fallback_active"


def test_formalize_refuses_if_raw_qac_directory_already_has_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    raw = tmp_path / "raw_qac"
    raw.mkdir()
    (raw / "morphology.txt").write_text("nie powinno tu byc", encoding="utf-8")
    monkeypatch.setattr("src.data.download_qac.QAC_RAW_DIR", raw)

    with pytest.raises(QacDownloadForbiddenError):
        formalize_qac_fallback(
            eqtb_tokens_path=tmp_path / "eqtb.parquet",
            artifact_path=tmp_path / "out.json",
        )
