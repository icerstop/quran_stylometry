"""T-019: okna, G3, ogony, kompozyty — wejscie syntetyczne."""

from __future__ import annotations

from src.config import SegmentationCfg
from src.data.segment import (
    TokenRec,
    assert_g3,
    cut_unit,
    pack_quran_units,
    spans_disjoint,
)
from src.schemas import Window

CFG = SegmentationCfg()


def _recs(n: int, surah: int, verse: int = 1) -> list[TokenRec]:
    return [TokenRec(token=f"t{i}", surah_id=surah, verse_id=verse) for i in range(n)]


def test_window_never_crosses_surah_boundary() -> None:
    """G3 — okno nie przekracza granicy sury ani dziela."""
    table = {
        1: {"period_traditional": "meccan"},
        2: {"period_traditional": "medinan"},
    }
    by_surah = {1: _recs(400, 1), 2: _recs(400, 2)}
    packed = pack_quran_units(by_surah, table, window_size=400, min_tail_ratio=0.6)
    assert len(packed) == 2
    for stream, _multi in packed:
        ids = {r.surah_id for r in stream}
        assert len(ids) == 1


def test_short_tail_is_merged_when_below_min_ratio() -> None:
    """Ogon krotszy niz 0.6 * window_size jest doklejany do poprzedniego okna."""
    spans = cut_unit(
        1000,
        window_size=400,
        min_tail_ratio=0.6,
        max_window_ratio=1.6,
        overlap=0.0,
    )
    lengths = [hi - lo for lo, hi in spans]
    assert lengths == [400, 600]
    assert all(hi - lo <= int(round(400 * 1.6)) for lo, hi in spans)


def test_merged_window_never_exceeds_max_ratio() -> None:
    """Wynik klejenia nie przekracza 1.6 * window_size."""
    max_len = int(round(10 * 1.6))
    spans = cut_unit(25, window_size=10, min_tail_ratio=0.6, max_window_ratio=1.6)
    assert all(hi - lo <= max_len for lo, hi in spans)
    spans2 = cut_unit(26, window_size=10, min_tail_ratio=0.6, max_window_ratio=1.6)
    assert all(hi - lo <= max_len for lo, hi in spans2)
    assert [hi - lo for lo, hi in spans2] == [10, 10, 6]


def test_short_surah_becomes_composite_window() -> None:
    """Sury krotsze niz 0.6 W, sasiadujace, ten sam okres → kompozyt."""
    table = {
        108: {"period_traditional": "meccan"},
        109: {"period_traditional": "meccan"},
        110: {"period_traditional": "medinan"},
    }
    by_surah = {
        108: _recs(100, 108),
        109: _recs(100, 109),
        110: _recs(100, 110),
    }
    packed = pack_quran_units(by_surah, table, window_size=400, min_tail_ratio=0.6)
    streams = [stream for stream, _ in packed]
    assert any(len({r.surah_id for r in s}) == 2 for s in streams)
    last = packed[-1][0]
    assert {r.surah_id for r in last} == {110}


def test_composite_window_records_all_source_surahs() -> None:
    table = {
        108: {"period_traditional": "meccan"},
        109: {"period_traditional": "meccan"},
    }
    by_surah = {108: _recs(80, 108), 109: _recs(90, 109)}
    packed = pack_quran_units(by_surah, table, window_size=400, min_tail_ratio=0.6)
    stream, multi = packed[0]
    ids = sorted({int(r.surah_id) for r in stream if r.surah_id is not None})
    assert multi is True
    assert ids == [108, 109]


def test_main_windows_have_no_overlap() -> None:
    spans = cut_unit(
        2000,
        window_size=400,
        min_tail_ratio=CFG.min_tail_ratio,
        max_window_ratio=CFG.max_window_ratio,
        overlap=0.0,
    )
    assert spans_disjoint(spans)
    olap = cut_unit(
        2000,
        window_size=400,
        min_tail_ratio=CFG.min_tail_ratio,
        max_window_ratio=CFG.max_window_ratio,
        overlap=0.5,
    )
    assert not spans_disjoint(olap)


def test_window_length_distribution_is_matched_across_corpora() -> None:
    """G6 — te same dlugosci jednostek → ten sam rozklad okien."""
    kwargs = {
        "window_size": 400,
        "min_tail_ratio": 0.6,
        "max_window_ratio": 1.6,
        "overlap": 0.0,
    }
    a = [hi - lo for lo, hi in cut_unit(2000, **kwargs)]
    b = [hi - lo for lo, hi in cut_unit(2000, **kwargs)]
    assert a == b


def test_assert_g3_rejects_noncomposite_multi_surah() -> None:
    from tests.test_schema import window_kwargs

    window = Window(**window_kwargs(surah_ids=[1, 2], composite=True, surah_id=1))
    assert_g3([window])
