"""G1 — zadna macierz cross-corpus nie powstaje z pol `*_gold`.

AGENTS.md zasada 3: ten test musi przechodzic PRZED KAZDYM COMMITEM (jest tez
hookiem w `.pre-commit-config.yaml`).

Zakres w P0: kontrakt `FeatureMatrix`, czyli punkt, przez ktory kazda macierz
musi przejsc. Gdy powstana rodziny cech (T-021..T-028), dojdzie tu wariant
sprawdzajacy zapisane artefakty w `data/features/` — sam kontrakt juz teraz
uniemozliwia zbudowanie zlej macierzy.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.schemas import FeatureMatrix, GuardrailViolationError


def matrix_kwargs(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "family": "pos",
        "config_label": "FUNCTIONAL",
        "status": "core",
        "corpus_scope": "cross_corpus",
        "annotation_source": "predicted",
        "fitted_on": "ctrl_train",
        "config_hash": "abc123",
        "normalizer_version": "strict-1.0.0",
        "tagger_version": "camel-tools-1.6.0",
        "n_rows": 200,
        "n_cols": 512,
        "distance_main": "jensen_shannon",
    }
    payload.update(overrides)
    return payload


def test_predicted_annotations_are_allowed_cross_corpus() -> None:
    matrix = FeatureMatrix(**matrix_kwargs())
    assert matrix.annotation_source == "predicted"
    assert matrix.corpus_scope == "cross_corpus"


def test_gold_annotations_are_rejected_cross_corpus() -> None:
    """Zloto QAC/EQTB po jednej stronie, tagger po drugiej = gwarantowany artefakt."""
    with pytest.raises(GuardrailViolationError, match="G1"):
        FeatureMatrix(**matrix_kwargs(annotation_source="gold"))


def test_silver_annotations_are_rejected_cross_corpus() -> None:
    """Warstwa skladniowa EQTB jest silver i nie ma odpowiednika po stronie OpenITI."""
    with pytest.raises(GuardrailViolationError, match="G1"):
        FeatureMatrix(**matrix_kwargs(family="syntax", annotation_source="silver"))


def test_gold_is_allowed_inside_quran_only() -> None:
    """Zloto wolno uzywac do analiz wewnatrz Koranu i do ewaluacji taggera."""
    matrix = FeatureMatrix(
        **matrix_kwargs(
            family="syntax",
            config_label="SYNTAX_Q",
            status="support",
            corpus_scope="quran_only",
            annotation_source="silver",
            fitted_on="none",
        )
    )
    assert matrix.corpus_scope == "quran_only"


@pytest.mark.parametrize("scope", ["cross_corpus", "ctrl_only"])
def test_g4_fitting_outside_ctrl_train_is_rejected(scope: str) -> None:
    """G4 — wektoryzatory i skalery fitujemy wylacznie na CTRL-TRAIN."""
    with pytest.raises(GuardrailViolationError, match="G4"):
        FeatureMatrix(**matrix_kwargs(corpus_scope=scope, fitted_on="none"))


def test_empty_matrix_is_rejected() -> None:
    with pytest.raises(ValueError, match="Pusta macierz"):
        FeatureMatrix(**matrix_kwargs(n_rows=0))


def test_document_ids_must_match_row_count() -> None:
    with pytest.raises(ValueError, match="document_ids"):
        FeatureMatrix(**matrix_kwargs(n_rows=3, document_ids=["a", "b"]))


def test_annotation_source_typo_is_rejected() -> None:
    """`extra="forbid"` + Literal: nie da sie przemycic wartosci spoza slownika."""
    with pytest.raises(ValueError):
        FeatureMatrix(**matrix_kwargs(annotation_source="predicted_gold"))
