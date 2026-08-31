"""Jeden tagger produkcyjny: CAMeL Tools + calima-msa-r13 (G1, T-014).

Farasa nie istnieje w tym module — 09_DECISIONS.md §1. Disambiguator MLE
na laptopie (configs/base.yaml, laptop_only.yaml). Wejscie: tokeny juz
znormalizowane profilem ``strict`` (G2), jeden token = slowo ortograficzne.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from src.annotate.gold import normalize_lemma
from src.annotate.tagset_map import camel_to_coarse, camel_to_eqtb
from src.data.normalize_arabic import normalize


class TaggerNotAvailableError(RuntimeError):
    """Brak camel-tools albo bazy calima-msa-r13 (``make setup-nlp``)."""


@dataclass(frozen=True)
class PredictedWord:
    surface: str
    surface_norm: str
    pos_raw: str
    pos_eqtb: str | None
    pos_coarse: str
    lemma_raw: str
    lemma_norm: str
    segments_norm: tuple[str, ...]


class SentenceTagger(Protocol):
    def tag_sentence(self, tokens: Sequence[str]) -> list[PredictedWord]: ...


def analysis_mapping(item: Any) -> dict[str, Any]:
    if item is None:
        return {}
    analysis = getattr(item, "analysis", item)
    if isinstance(analysis, dict):
        return analysis
    if hasattr(analysis, "items"):
        return dict(analysis)
    return {}


def parse_bw_segments(bw: str, *, profile: str = "strict") -> tuple[str, ...]:
    """Pole ``bw`` CALIMA: ``bi/PREP+som/NOUN+hu/PRON``. Zwraca formy AR znorm."""
    return tuple(form for form, _pos in parse_bw_with_pos(bw, profile=profile))


def parse_bw_with_pos(bw: str, *, profile: str = "strict") -> list[tuple[str, str]]:
    """Jak ``parse_bw_segments``, ale z POS segmentu (PREP/NOUN/PRON/...)."""
    if not bw or bw in {"_", "NOAN"}:
        return []
    out: list[tuple[str, str]] = []
    for chunk in bw.split("+"):
        piece = chunk.strip()
        if not piece or piece == "0":
            continue
        if "/" in piece:
            form, pos = piece.split("/", 1)
        else:
            form, pos = piece, ""
        form = form.strip()
        if not form or form == "0":
            continue
        norm = normalize_lemma(form, profile=profile)
        if not norm:
            continue
        out.append((norm, pos.strip().upper()))
    return out


def predicted_from_analysis(
    surface: str,
    analysis: dict[str, Any],
    *,
    profile: str = "strict",
) -> PredictedWord:
    surface_norm = normalize(surface, profile) if surface else ""  # type: ignore[arg-type]
    pos_raw = str(analysis.get("pos") or analysis.get("pos_type") or "").strip().lower()
    lemma_raw = str(analysis.get("lex") or analysis.get("lemma") or "").strip()
    bw = str(analysis.get("bw") or "")
    segments = parse_bw_segments(bw, profile=profile)
    if not segments and surface_norm:
        segments = (surface_norm,)
    return PredictedWord(
        surface=surface,
        surface_norm=surface_norm,
        pos_raw=pos_raw,
        pos_eqtb=camel_to_eqtb(pos_raw) if pos_raw else None,
        pos_coarse=camel_to_coarse(pos_raw) if pos_raw else "PART",
        lemma_raw=lemma_raw,
        lemma_norm=normalize_lemma(lemma_raw, profile=profile),
        segments_norm=segments,
    )


class StubTagger:
    """Tagger do testow — bez camel-tools, bez sieci."""

    def __init__(self, sentences: dict[tuple[str, ...], list[PredictedWord]] | None = None) -> None:
        self._sentences = sentences or {}

    def tag_sentence(self, tokens: Sequence[str]) -> list[PredictedWord]:
        key = tuple(tokens)
        if key in self._sentences:
            return list(self._sentences[key])
        return [
            PredictedWord(
                surface=tok,
                surface_norm=tok,
                pos_raw="noun",
                pos_eqtb="N",
                pos_coarse="NOUN",
                lemma_raw=tok,
                lemma_norm=tok,
                segments_norm=(tok,) if tok else (),
            )
            for tok in tokens
        ]


class CamelMLETagger:
    """CAMeL MLE + calima-msa-r13. Lazy load — konstruktor nie wymaga bazy w testach."""

    def __init__(
        self,
        *,
        database: str = "calima-msa-r13",
        profile: str = "strict",
        disambiguator: Any | None = None,
    ) -> None:
        self.database = database
        self.profile = profile
        self._disambiguator = disambiguator

    def _load(self) -> Any:
        if self._disambiguator is not None:
            return self._disambiguator
        try:
            from camel_tools.disambig.mle import MLEDisambiguator
        except ImportError as exc:
            raise TaggerNotAvailableError(
                "camel-tools nie jest zainstalowane. Uruchom `make setup-nlp`."
            ) from exc
        try:
            self._disambiguator = MLEDisambiguator.pretrained(self.database)
        except Exception as exc:  # baza moze nie byc pobrana
            raise TaggerNotAvailableError(
                f"Baza {self.database} niedostepna ({exc}). Uruchom `make setup-nlp` "
                "(camel_data -i light)."
            ) from exc
        return self._disambiguator

    def tag_sentence(self, tokens: Sequence[str]) -> list[PredictedWord]:
        mle = self._load()
        words = [tok if tok else "" for tok in tokens]
        if not words:
            return []
        disambig = mle.disambiguate(words)
        predicted: list[PredictedWord] = []
        for surface, item in zip(words, disambig, strict=True):
            analyses = getattr(item, "analyses", None) or []
            top = analyses[0] if analyses else None
            predicted.append(
                predicted_from_analysis(surface, analysis_mapping(top), profile=self.profile)
            )
        return predicted
