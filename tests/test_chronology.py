"""T-018: Spearman ρ, 13 roznic traditional/noldeke, shuffle, FIG-06b."""

from __future__ import annotations

from src.data.chronology import (
    load_chronologies_table,
    rank_disagreements,
    run_chronology_agreement,
    spearman_matrix,
)
from src.viz.fig06b_chronology import SPEC


def test_csv_has_three_orderings_and_no_sadeghi() -> None:
    frame = load_chronologies_table()
    assert len(frame) == 114
    assert "order_sadeghi" not in frame.columns
    assert {"order_canonical", "order_traditional", "order_noldeke"} <= set(frame.columns)


def test_traditional_noldeke_differ_on_thirteen_surahs() -> None:
    """09_DECISIONS §2.4 / 03_DATA §8 — liczba liczona, nie przepisana."""
    frame = load_chronologies_table()
    differ = rank_disagreements(frame, "order_traditional", "order_noldeke")
    assert len(differ) == 13
    assert 110 in differ
    assert 62 in differ


def test_spearman_traditional_noldeke_near_one_canonical_is_the_contrast() -> None:
    frame = load_chronologies_table()
    labels, matrix = spearman_matrix(frame)
    idx = {label: i for i, label in enumerate(labels)}
    rho_tn = matrix[idx["traditional"]][idx["noldeke"]]
    rho_ct = matrix[idx["canonical"]][idx["traditional"]]
    assert rho_tn > 0.99
    assert abs(rho_ct) < abs(rho_tn)


def test_shuffle_control_is_near_zero() -> None:
    payload = run_chronology_agreement(seed=20260830, n_perm=80)
    mean = float(payload["shuffle"]["rho_mean"])
    assert abs(mean) < 0.15


def test_fig06b_declares_shuffle_and_excludes_sadeghi() -> None:
    assert SPEC.fig_id == "FIG-06b"
    assert SPEC.kind == "result"
    assert SPEC.control_anchor
    assert "shuffle" in SPEC.control_anchor.lower()
    assert "canonical" in SPEC.shows.lower()
    assert "noldeke" in SPEC.shows.lower()
    assert "cairo" not in SPEC.shows.lower()
    assert "paywall" in SPEC.do_not_conclude.lower()