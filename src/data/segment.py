"""T-019: segmentacja na okna (docs/03_DATA.md §6, guardrail G3).

Okno nigdy nie przekracza surah_id (Koran) ani book_id (CTRL). Reszta krotsza
niz ``min_tail_ratio * window_size`` jest doklejana do poprzedniego okna tej
samej jednostki (cap ``max_window_ratio``). Krotkie sury lacza sie w okna
kompozytowe tylko z sasiadami kanonicznymi w tym samym ``period_traditional``.
CTRL nigdy nie skleja dwoch book_id.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, get_args

import pandas as pd

from src.config import SegmentationCfg
from src.data.detect_quran_quotes import (
    EQTB_TOKENS_PATH,
    OrthoWord,
    load_genre_map,
    quran_ortho_words,
)
from src.paths import (
    CHRONOLOGIES_PATH,
    CTRL_CAPPED_MANIFEST_PATH,
    CTRL_MANIFEST_PATH,
    GENRES_PATH,
    OPENITI_CLEAN_DIR,
    SEGMENTATION_REPORT_PATH,
    windows_dir,
)
from src.schemas import Chronology, Genre, PeriodBucket, PeriodLabel, Split, Window
from src.utils.io import ensure_dir, write_json

CTRL_SPLIT_PLACEHOLDER: Split = "ctrl_test"


@dataclass(frozen=True)
class TokenRec:
    token: str
    surah_id: int | None = None
    verse_id: int | None = None


def cut_unit(
    n_tokens: int,
    *,
    window_size: int,
    min_tail_ratio: float,
    max_window_ratio: float,
    overlap: float = 0.0,
) -> list[tuple[int, int]]:
    """Zwraca polowki [lo, hi) na strumieniu jednej jednostki."""
    if n_tokens <= 0:
        return []
    min_tail = max(1, int(round(window_size * min_tail_ratio)))
    max_len = max(window_size, int(round(window_size * max_window_ratio)))
    if overlap <= 0.0:
        return _cut_no_overlap(n_tokens, window_size, min_tail, max_len)
    step = max(1, int(round(window_size * (1.0 - overlap))))
    spans: list[tuple[int, int]] = []
    start = 0
    while start < n_tokens:
        end = min(n_tokens, start + window_size)
        remainder = n_tokens - start
        if spans and remainder < min_tail:
            prev_lo, _prev_hi = spans[-1]
            glued = min(n_tokens, prev_lo + max_len)
            spans[-1] = (prev_lo, glued)
            if glued < n_tokens:
                spans.append((glued, n_tokens))
            break
        spans.append((start, end))
        if end >= n_tokens:
            break
        start += step
    return spans


def _cut_no_overlap(
    n_tokens: int, window_size: int, min_tail: int, max_len: int
) -> list[tuple[int, int]]:
    if n_tokens <= max_len and n_tokens < window_size + min_tail:
        # Jedno okno, jesli calosc miesci sie w capie i nie da sie odciac
        # pelnego okna z ogonem >= min_tail.
        if n_tokens <= window_size:
            return [(0, n_tokens)]
    spans: list[tuple[int, int]] = []
    i = 0
    while i < n_tokens:
        remaining = n_tokens - i
        if remaining <= window_size:
            if spans and remaining < min_tail:
                prev_lo, _prev_hi = spans[-1]
                merged = n_tokens - prev_lo
                if merged <= max_len:
                    spans[-1] = (prev_lo, n_tokens)
                else:
                    spans.append((i, n_tokens))
            else:
                spans.append((i, n_tokens))
            break
        spans.append((i, i + window_size))
        i += window_size
    return spans


def parse_verse_spec(spec: str | float | None) -> set[int]:
    if spec is None:
        return set()
    text = str(spec).strip()
    if not text or text.lower() in {"nan", "none", "-"}:
        return set()
    out: set[int] = set()
    for part in text.replace(";", ",").split(","):
        piece = part.strip()
        if not piece:
            continue
        if "-" in piece:
            lo_s, hi_s = piece.split("-", 1)
            out.update(range(int(lo_s), int(hi_s) + 1))
        else:
            out.add(int(piece))
    return out


def load_chronologies(path: Path = CHRONOLOGIES_PATH) -> dict[int, dict[str, Any]]:
    frame = pd.read_csv(path)
    rows: dict[int, dict[str, Any]] = {}
    for rec in frame.to_dict("records"):
        sid = int(rec["surah_id"])
        rows[sid] = rec
    return rows


def chronology_for_span(
    surah_ids: Sequence[int],
    verses: Sequence[int],
    table: dict[int, dict[str, Any]],
) -> Chronology:
    periods: list[str] = []
    mixed = False
    composite_flag = 0
    orders: dict[str, int | None] = {
        "order_canonical": None,
        "order_traditional": None,
        "order_noldeke": None,
    }
    verse_set = {int(v) for v in verses if v}
    for sid in surah_ids:
        row = table.get(int(sid)) or {}
        period = str(row.get("period_traditional") or "") or None
        if period:
            periods.append(period)
        if int(row.get("composite_flag") or 0):
            composite_flag = 1
        exceptions = parse_verse_spec(row.get("exception_verses"))
        exc_period = str(row.get("exception_period") or "") or None
        if exceptions and verse_set & exceptions and exc_period and exc_period != period:
            mixed = True
        if len(surah_ids) == 1:
            for key in orders:
                val = row.get(key)
                orders[key] = int(val) if val == val and val is not None else None
    unique = {p for p in periods if p in {"meccan", "medinan", "mixed"}}
    if mixed or len(unique) > 1:
        period_label: PeriodLabel | None = "mixed"
    elif unique:
        period_label = next(iter(unique))  # type: ignore[assignment]
    else:
        period_label = None
    return Chronology(
        period_traditional=period_label,
        order_canonical=orders["order_canonical"],
        order_traditional=orders["order_traditional"],
        order_noldeke=orders["order_noldeke"],
        composite_flag=composite_flag,
        exception_period=None if not mixed else "mixed",
    )


def _period_of(sid: int, table: dict[int, dict[str, Any]]) -> str:
    return str((table.get(sid) or {}).get("period_traditional") or "")


def pack_quran_units(
    by_surah: dict[int, list[TokenRec]],
    table: dict[int, dict[str, Any]],
    *,
    window_size: int,
    min_tail_ratio: float,
) -> list[tuple[list[TokenRec], bool]]:
    """Zwraca listy tokenow do ciecia: (stream, force_composite_if_multi)."""
    min_len = max(1, int(round(window_size * min_tail_ratio)))
    surahs = sorted(by_surah)
    units: list[tuple[list[TokenRec], bool]] = []
    chain: list[int] = []

    def flush() -> None:
        nonlocal chain
        if not chain:
            return
        stream: list[TokenRec] = []
        for sid in chain:
            stream.extend(by_surah[sid])
        units.append((stream, len(chain) > 1))
        chain = []

    for sid in surahs:
        recs = by_surah[sid]
        if len(recs) >= min_len:
            flush()
            units.append((recs, False))
            continue
        if (
            chain
            and sid == chain[-1] + 1
            and _period_of(sid, table) == _period_of(chain[-1], table)
            and _period_of(sid, table)
        ):
            chain.append(sid)
        else:
            flush()
            chain = [sid]
    flush()
    return units


def spans_disjoint(spans: Sequence[tuple[int, int]]) -> bool:
    ordered = sorted(spans)
    for (lo, hi), (lo2, _hi2) in zip(ordered, ordered[1:], strict=False):
        if lo2 < hi:
            return False
    return True


def _safe_genre(raw: str) -> Genre:
    allowed = set(get_args(Genre))
    return raw if raw in allowed else "other"  # type: ignore[return-value]


def _period_bucket(death: int | None, near_max: int = 500) -> PeriodBucket:
    if death is None:
        return "na"
    return "near" if int(death) <= near_max else "broad"


def build_window(
    *,
    document_id: str,
    corpus: str,
    split: Split,
    recs: Sequence[TokenRec],
    composite: bool,
    overlapping: bool,
    genre: Genre,
    normalizer_version: str,
    tagger_version: str,
    chronology: Chronology,
    author_id: str | None = None,
    book_id: str | None = None,
    version_id: str | None = None,
    death_date_ah: int | None = None,
    period_bucket: PeriodBucket = "na",
) -> Window:
    tokens = [r.token for r in recs]
    surah_ids = sorted({int(r.surah_id) for r in recs if r.surah_id is not None})
    verses = [int(r.verse_id) for r in recs if r.verse_id is not None]
    n_verses = len(set(verses)) if verses else 0
    surah_id = surah_ids[0] if len(surah_ids) == 1 else (surah_ids[0] if surah_ids else None)
    if composite and surah_ids:
        surah_id = surah_ids[0]
    mean_verse_len = (len(tokens) / n_verses) if n_verses else None
    return Window(
        document_id=document_id,
        corpus=corpus,  # type: ignore[arg-type]
        split=split,
        author_id=author_id,
        book_id=book_id,
        version_id=version_id,
        genre=genre,
        death_date_ah=death_date_ah,
        period_bucket=period_bucket,
        surah_id=surah_id,
        surah_ids=surah_ids,
        verse_start=min(verses) if verses else None,
        verse_end=max(verses) if verses else None,
        composite=composite,
        overlapping=overlapping,
        chronology=chronology,
        text_norm_strict=" ".join(tokens),
        tokens=tokens,
        n_tokens=len(tokens),
        n_segments=0,
        n_verses=n_verses,
        mean_verse_len=mean_verse_len,
        annotation_source="predicted",
        normalizer_version=normalizer_version,
        tagger_version=tagger_version,
    )


def assert_g3(windows: Sequence[Window]) -> None:
    for window in windows:
        if not window.composite and len(window.surah_ids) > 1:
            raise AssertionError(f"{window.document_id}: niekompozytowe okno obejmuje wiele sur (G3)")
        if window.corpus == "quran" and window.book_id is not None:
            raise AssertionError(f"{window.document_id}: okno Koranu ma book_id")
        if window.corpus == "ctrl" and window.book_id is None:
            raise AssertionError(f"{window.document_id}: okno CTRL bez book_id")


def segment_streams(
    units: Sequence[tuple[list[TokenRec], bool]],
    *,
    cfg: SegmentationCfg,
    overlap: float,
    overlapping: bool,
    make_window: Any,
) -> list[Window]:
    windows: list[Window] = []
    for stream, multi_source in units:
        n = len(stream)
        spans = cut_unit(
            n,
            window_size=cfg.window_size,
            min_tail_ratio=cfg.min_tail_ratio,
            max_window_ratio=cfg.max_window_ratio,
            overlap=overlap,
        )
        if overlapping and not spans_disjoint(spans):
            pass  # expected
        elif not overlapping and not spans_disjoint(spans):
            raise AssertionError("okna glowne musza byc rozlaczne (overlap=0)")
        for idx, (lo, hi) in enumerate(spans):
            recs = stream[lo:hi]
            surahs = sorted({int(r.surah_id) for r in recs if r.surah_id is not None})
            composite = multi_source and len(surahs) > 1
            windows.append(make_window(recs, idx, composite=composite, overlapping=overlapping))
    return windows


def _load_ctrl_meta() -> dict[str, dict[str, Any]]:
    meta: dict[str, dict[str, Any]] = {}
    if CTRL_CAPPED_MANIFEST_PATH.exists():
        cap = pd.read_csv(CTRL_CAPPED_MANIFEST_PATH)
        for rec in cap.to_dict("records"):
            uri = str(rec.get("version_uri") or "")
            meta[uri] = {
                "author_id": str(rec.get("author_id") or "") or None,
                "book_id": str(rec.get("book_id") or "") or None,
                "version_id": uri,
            }
    if CTRL_MANIFEST_PATH.exists():
        man = pd.read_csv(CTRL_MANIFEST_PATH)
        for rec in man.to_dict("records"):
            uri = str(rec.get("version_uri") or "")
            if uri not in meta:
                meta[uri] = {}
            death = rec.get("death_date_ah")
            try:
                death_i = int(float(death)) if death == death and death is not None else None
            except (TypeError, ValueError):
                death_i = None
            meta[uri]["death_date_ah"] = death_i
            meta[uri].setdefault("author_id", str(rec.get("author_id") or "") or None)
            meta[uri].setdefault("book_id", str(rec.get("book") or "") or None)
            meta[uri].setdefault("version_id", uri)
    return meta


def _window_row(window: Window) -> dict[str, Any]:
    dumped = window.model_dump(mode="json")
    chrono = dumped.pop("chronology")
    dumped.pop("predicted", None)
    dumped.pop("gold", None)
    for key, val in chrono.items():
        dumped[f"chrono_{key}"] = val
    return dumped


def write_windows_parquet(windows: Sequence[Window], path: Path) -> Path:
    ensure_dir(path.parent)
    rows = [_window_row(w) for w in windows]
    frame = pd.DataFrame(rows)
    frame.to_parquet(path, index=False)
    return path


def _summarize(windows: Sequence[Window]) -> dict[str, Any]:
    n_comp = sum(1 for w in windows if w.composite)
    tok_comp = sum(w.n_tokens for w in windows if w.composite)
    lengths = [w.n_tokens for w in windows]
    mean = (sum(lengths) / len(lengths)) if lengths else 0.0
    if len(lengths) >= 2:
        mu = mean
        var = sum((x - mu) ** 2 for x in lengths) / (len(lengths) - 1)
        std = var**0.5
    else:
        std = 0.0
    return {
        "n_windows": len(windows),
        "n_composite": n_comp,
        "tokens_in_composite": tok_comp,
        "n_tokens": sum(lengths),
        "length_mean": mean,
        "length_std": std,
        "length_min": min(lengths) if lengths else 0,
        "length_max": max(lengths) if lengths else 0,
        "n_overlapping": sum(1 for w in windows if w.overlapping),
    }


def segment_quran(
    words: Sequence[OrthoWord],
    table: dict[int, dict[str, Any]],
    *,
    cfg: SegmentationCfg,
    overlap: float,
    overlapping: bool,
    normalizer_version: str,
    tagger_version: str,
) -> list[Window]:
    by_surah: dict[int, list[TokenRec]] = {}
    for word in words:
        by_surah.setdefault(word.surah_id, []).append(
            TokenRec(token=word.token, surah_id=word.surah_id, verse_id=word.verse_id)
        )
    packed = pack_quran_units(
        by_surah, table, window_size=cfg.window_size, min_tail_ratio=cfg.min_tail_ratio
    )

    def maker(
        recs: Sequence[TokenRec], idx: int, *, composite: bool, overlapping: bool
    ) -> Window:
        surahs = sorted({int(r.surah_id) for r in recs if r.surah_id is not None})
        verses = [int(r.verse_id) for r in recs if r.verse_id is not None]
        chrono = chronology_for_span(surahs, verses, table)
        if composite:
            doc = f"quran_c{surahs[0]:03d}-{surahs[-1]:03d}_w{idx:03d}"
        else:
            sid = surahs[0] if surahs else 0
            doc = f"quran_s{sid:03d}_w{idx:03d}"
        return build_window(
            document_id=doc,
            corpus="quran",
            split="target",
            recs=recs,
            composite=composite,
            overlapping=overlapping,
            genre="quran",
            normalizer_version=normalizer_version,
            tagger_version=tagger_version,
            chronology=chrono,
        )

    windows = segment_streams(
        packed, cfg=cfg, overlap=overlap, overlapping=overlapping, make_window=maker
    )
    assert_g3(windows)
    return windows


def segment_ctrl(
    ctrl_dir: Path,
    *,
    cfg: SegmentationCfg,
    overlap: float,
    overlapping: bool,
    normalizer_version: str,
    tagger_version: str,
    limit_books: int | None = None,
) -> list[Window]:
    meta = _load_ctrl_meta()
    genres = load_genre_map(GENRES_PATH)
    books = sorted(
        p
        for p in ctrl_dir.iterdir()
        if p.is_file() and p.name != "manifest.csv" and not p.name.endswith(".done")
    )
    if limit_books is not None:
        books = books[: int(limit_books)]
    windows: list[Window] = []
    for path in books:
        tokens = path.read_text(encoding="utf-8").split()
        if not tokens:
            continue
        recs = [TokenRec(token=tok) for tok in tokens]
        info = meta.get(path.name) or {}
        genre = _safe_genre(genres.get(path.name, "other"))
        death = info.get("death_date_ah")
        spans = cut_unit(
            len(recs),
            window_size=cfg.window_size,
            min_tail_ratio=cfg.min_tail_ratio,
            max_window_ratio=cfg.max_window_ratio,
            overlap=overlap,
        )
        if not overlapping and not spans_disjoint(spans):
            raise AssertionError(f"{path.name}: okna glowne nachodza (G3)")
        for idx, (lo, hi) in enumerate(spans):
            slice_recs = recs[lo:hi]
            windows.append(
                build_window(
                    document_id=f"ctrl_{path.name}_w{idx:04d}",
                    corpus="ctrl",
                    split=CTRL_SPLIT_PLACEHOLDER,
                    recs=slice_recs,
                    composite=False,
                    overlapping=overlapping,
                    genre=genre,
                    normalizer_version=normalizer_version,
                    tagger_version=tagger_version,
                    chronology=Chronology(),
                    author_id=info.get("author_id"),
                    book_id=info.get("book_id") or path.name,
                    version_id=info.get("version_id") or path.name,
                    death_date_ah=int(death) if death is not None else None,
                    period_bucket=_period_bucket(
                        int(death) if death is not None else None
                    ),
                )
            )
    assert_g3(windows)
    return windows


def run_segmentation(
    *,
    cfg: SegmentationCfg,
    normalizer_version: str,
    tagger_version: str,
    profile: str = "strict",
    eqtb_path: Path = EQTB_TOKENS_PATH,
    ctrl_dir: Path = OPENITI_CLEAN_DIR,
    limit_books: int | None = None,
    sizes: Sequence[int] | None = None,
    write_olap: bool = True,
) -> dict[str, Any]:
    if not eqtb_path.exists():
        raise FileNotFoundError(f"Brak {eqtb_path} (T-009)")
    if not ctrl_dir.is_dir():
        raise FileNotFoundError(f"Brak {ctrl_dir} (T-016)")
    eqtb = pd.read_parquet(eqtb_path)
    words = quran_ortho_words(eqtb, profile=profile)
    table = load_chronologies()
    size_list = list(sizes) if sizes is not None else [cfg.window_size, *cfg.window_size_sensitivity]
    # unique preserve order
    seen: set[int] = set()
    ordered_sizes: list[int] = []
    for s in size_list:
        if s not in seen:
            seen.add(s)
            ordered_sizes.append(int(s))

    report: dict[str, Any] = {
        "task": "T-019",
        "window_size_main": cfg.window_size,
        "sizes": {},
        "ctrl_split_placeholder": CTRL_SPLIT_PLACEHOLDER,
        "note": "split CTRL = ctrl_test do T-020 (author-level). T-020 nadpisze splits.json.",
    }
    for size in ordered_sizes:
        local_cfg = SegmentationCfg(
            window_size=size,
            window_size_sensitivity=list(cfg.window_size_sensitivity),
            overlap=0.0,
            overlap_local=cfg.overlap_local,
            respect_boundaries=list(cfg.respect_boundaries),
            min_tail_ratio=cfg.min_tail_ratio,
            max_window_ratio=cfg.max_window_ratio,
        )
        q_win = segment_quran(
            words,
            table,
            cfg=local_cfg,
            overlap=0.0,
            overlapping=False,
            normalizer_version=normalizer_version,
            tagger_version=tagger_version,
        )
        c_win = segment_ctrl(
            ctrl_dir,
            cfg=local_cfg,
            overlap=0.0,
            overlapping=False,
            normalizer_version=normalizer_version,
            tagger_version=tagger_version,
            limit_books=limit_books,
        )
        out = windows_dir(size, overlapping=False)
        ensure_dir(out)
        write_windows_parquet(q_win, out / "quran.parquet")
        write_windows_parquet(c_win, out / "ctrl.parquet")
        report["sizes"][str(size)] = {
            "quran": _summarize(q_win),
            "ctrl": _summarize(c_win),
            "dir": str(out.as_posix()),
        }

    if write_olap:
        olap_cfg = SegmentationCfg(
            window_size=cfg.window_size,
            window_size_sensitivity=list(cfg.window_size_sensitivity),
            overlap=cfg.overlap_local,
            overlap_local=cfg.overlap_local,
            respect_boundaries=list(cfg.respect_boundaries),
            min_tail_ratio=cfg.min_tail_ratio,
            max_window_ratio=cfg.max_window_ratio,
        )
        q_olap = segment_quran(
            words,
            table,
            cfg=olap_cfg,
            overlap=cfg.overlap_local,
            overlapping=True,
            normalizer_version=normalizer_version,
            tagger_version=tagger_version,
        )
        c_olap = segment_ctrl(
            ctrl_dir,
            cfg=olap_cfg,
            overlap=cfg.overlap_local,
            overlapping=True,
            normalizer_version=normalizer_version,
            tagger_version=tagger_version,
            limit_books=limit_books,
        )
        out_olap = windows_dir(cfg.window_size, overlapping=True)
        ensure_dir(out_olap)
        write_windows_parquet(q_olap, out_olap / "quran.parquet")
        write_windows_parquet(c_olap, out_olap / "ctrl.parquet")
        report["sizes"][f"{cfg.window_size}_olap"] = {
            "quran": _summarize(q_olap),
            "ctrl": _summarize(c_olap),
            "dir": str(out_olap.as_posix()),
            "overlap": cfg.overlap_local,
        }
    return report


def write_segmentation_report(
    payload: dict[str, Any],
    *,
    path: Path = SEGMENTATION_REPORT_PATH,
    config_hash: str | None = None,
) -> Path:
    out = dict(payload)
    out["config_hash"] = config_hash
    write_json(path, out)
    return path
