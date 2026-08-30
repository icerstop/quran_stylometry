"""Kontrakty I/O (T-007). Schemat rekordu wg docs/03_DATA.md §9.

Dwie rzeczy sa tu zaprojektowane tak, zeby naruszenie guardraila bylo
niemozliwe przez przypadek, a nie tylko zabronione w dokumentacji:

* pola `*_pred` i `*_gold` sa rozdzielone na poziomie typu (`Annotations`),
  a `FeatureMatrix` deklaruje `annotation_source` i `corpus_scope`; macierz
  `gold` w zasiegu `cross_corpus` jest odrzucana przy konstrukcji (G1);
* `Window` odrzuca rekord bez `split` i z `n_tokens == 0`.

ROZBIEZNOSC W DOKUMENTACJI (zgloszona, nie naprawiona):
docs/03_DATA.md §9 wymienia pola `order_cairo` i `order_sadeghi`, natomiast
docs/09_DECISIONS.md §2.4 definiuje `order_canonical / order_traditional /
order_noldeke` i usuwa `order_sadeghi` z designu. Naglowek 03_DATA.md mowi
wprost: "Przy rozbieznosci wygrywa 09_DECISIONS.md" — i tak tu zrobiono.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CorpusKind = Literal["quran", "ctrl", "pseudo", "mixture", "anchor"]
Split = Literal["ctrl_train", "ctrl_calib", "ctrl_test", "target"]
PeriodBucket = Literal["near", "broad", "na"]
PeriodLabel = Literal["meccan", "medinan", "mixed"]
AnnotationSource = Literal["predicted", "gold", "silver"]
CorpusScope = Literal["quran_only", "ctrl_only", "cross_corpus"]
FamilyStatus = Literal["core", "core_baseline", "support", "circular", "exploratory"]

# Zamknieta lista gatunkow z docs/03_DATA.md §3 + `quran` dla korpusu docelowego.
# Przypisanie jest regulowe (09_DECISIONS.md §4), bez etapu recznego etykietowania.
Genre = Literal[
    "quran",
    "tafsir",
    "hadith_collection",
    "history",
    "fiqh",
    "adab_prose",
    "maqamat_saj",
    "poetry_diwan",
    "prayer_sermon",
    "theology",
    "biography",
    "other",
]


class GuardrailViolationError(Exception):
    """Naruszenie guardraila G1-G9. Wynik nie idzie do raportu.

    Swiadomie NIE dziedziczy po `ValueError`: pydantic zamienia `ValueError`
    podniesiony w walidatorze na `ValidationError`, przez co zlamanie guardraila
    wygladaloby jak zwykla literowka w danych. Naruszenie G1 czy G4 jest bledem
    metodologicznym i ma sie propagowac wlasnym typem, ktorego nie lapie zadne
    ogolne `except ValueError`.
    """


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PredictedAnnotations(_Strict):
    """Tagi z taggera produkcyjnego. Jedyne dozwolone w porownaniu cross-corpus (G1)."""

    segments: list[str] = Field(default_factory=list)
    lemmas_pred: list[str] = Field(default_factory=list)
    pos_pred: list[str] = Field(default_factory=list)
    morph_pred: list[str] = Field(default_factory=list)


class GoldAnnotations(_Strict):
    """Zloto z EQTB/QAC. Dozwolone WYLACZNIE do ewaluacji taggera i analiz
    wewnatrz Koranu (03_DATA.md §5). Nigdy jako cechy cross-corpus."""

    lemmas_gold: list[str] = Field(default_factory=list)
    pos_gold: list[str] = Field(default_factory=list)
    morph_gold: list[str] = Field(default_factory=list)
    deprel_gold: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.lemmas_gold or self.pos_gold or self.morph_gold or self.deprel_gold)


class Chronology(_Strict):
    """Uporzadkowania z 09_DECISIONS.md §2.4. Bez `order_sadeghi` — usuniete z designu."""

    period_traditional: PeriodLabel | None = None
    order_canonical: int | None = None
    order_traditional: int | None = None
    order_noldeke: int | None = None
    composite_flag: int = 0
    exception_period: PeriodLabel | None = None


class Window(_Strict):
    """Okno segmentacyjne — podstawowa jednostka analizy (G3)."""

    document_id: str
    corpus: CorpusKind
    split: Split

    author_id: str | None = None
    book_id: str | None = None
    version_id: str | None = None
    genre: Genre
    death_date_ah: int | None = None
    period_bucket: PeriodBucket = "na"

    surah_id: int | None = None
    surah_ids: list[int] = Field(default_factory=list)
    verse_start: int | None = None
    verse_end: int | None = None
    composite: bool = False
    overlapping: bool = False

    chronology: Chronology = Field(default_factory=Chronology)

    text_norm_strict: str = ""
    text_norm_light: str = ""
    tokens: list[str] = Field(default_factory=list)
    predicted: PredictedAnnotations = Field(default_factory=PredictedAnnotations)
    gold: GoldAnnotations = Field(default_factory=GoldAnnotations)

    n_tokens: int
    n_segments: int = 0
    n_verses: int = 0
    mean_verse_len: float | None = None

    annotation_source: AnnotationSource = "predicted"
    normalizer_version: str
    tagger_version: str

    @model_validator(mode="after")
    def _check_invariants(self) -> Window:
        if self.n_tokens <= 0:
            raise ValueError(f"{self.document_id}: n_tokens musi byc > 0, dostano {self.n_tokens}")

        # G3: okno nie przekracza granicy sury ani dziela. Okno niekompozytowe
        # obejmujace wiele sur oznacza blad segmentacji, nie ciekawy przypadek.
        if not self.composite and len(self.surah_ids) > 1:
            raise ValueError(
                f"{self.document_id}: okno niekompozytowe obejmuje {len(self.surah_ids)} sur (G3)"
            )
        if self.corpus == "quran" and self.book_id is not None:
            raise ValueError(f"{self.document_id}: okno Koranu nie ma `book_id`")
        if self.surah_id is not None and self.surah_ids and self.surah_id not in self.surah_ids:
            raise ValueError(f"{self.document_id}: `surah_id` spoza `surah_ids`")
        return self


class FeatureMatrix(_Strict):
    """Metadane macierzy cech. Egzekwuje G1 i G4 przy konstrukcji."""

    family: str
    config_label: str
    status: FamilyStatus
    corpus_scope: CorpusScope
    annotation_source: AnnotationSource
    fitted_on: Literal["ctrl_train", "none"]

    config_hash: str
    normalizer_version: str
    tagger_version: str

    n_rows: int
    n_cols: int
    document_ids: list[str] = Field(default_factory=list)
    distance_main: str = "cosine"
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _enforce_guardrails(self) -> FeatureMatrix:
        # G1 — zadna macierz porownujaca Koran z korpusem kontrolnym nie moze
        # pochodzic z pol *_gold ani z warstwy silver EQTB.
        if self.corpus_scope == "cross_corpus" and self.annotation_source != "predicted":
            raise GuardrailViolationError(
                f"G1: rodzina '{self.family}' w zasiegu cross_corpus uzywa anotacji "
                f"'{self.annotation_source}'. Dozwolone jest wylacznie 'predicted' "
                "(ten sam tagger po obu stronach porownania)."
            )
        # G4 — cokolwiek dotyka CTRL, musi byc fitowane wylacznie na CTRL-TRAIN.
        if self.corpus_scope in ("cross_corpus", "ctrl_only") and self.fitted_on != "ctrl_train":
            raise GuardrailViolationError(
                f"G4: rodzina '{self.family}' deklaruje fitted_on='{self.fitted_on}'. "
                "Wektoryzatory i skalery fitujemy wylacznie na CTRL-TRAIN."
            )
        if self.n_rows <= 0 or self.n_cols <= 0:
            raise ValueError(f"Pusta macierz cech: {self.n_rows}x{self.n_cols}")
        if self.document_ids and len(self.document_ids) != self.n_rows:
            raise ValueError(f"len(document_ids)={len(self.document_ids)} != n_rows={self.n_rows}")
        return self


class ExperimentResult(_Strict):
    """Wynik eksperymentu z E-01..E-14. Kazda metryka niesie swoja niepewnosc
    albo jawnie deklaruje, ze jej nie ma (08_REPO.md §3)."""

    experiment_id: str
    task: str
    config_hash: str
    representations: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    ci: dict[str, list[float]] = Field(default_factory=dict)
    uncertainty_declared: bool
    control_anchor: str | None = None
    passed: bool | None = None
    criterion: str = ""
    figures: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    note: str = ""

    @model_validator(mode="after")
    def _check_uncertainty(self) -> ExperimentResult:
        if self.uncertainty_declared and not self.ci:
            raise ValueError(
                f"{self.experiment_id}: uncertainty_declared=True, ale brak przedzialow w `ci`"
            )
        for name, bounds in self.ci.items():
            if len(bounds) != 2 or bounds[0] > bounds[1]:
                raise ValueError(f"{self.experiment_id}: przedzial '{name}' nie jest [lo, hi]")
        return self
