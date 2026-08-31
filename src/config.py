"""Warstwa configow (T-002).

Kontrakt: kazdy artefakt jest zapisywany z `config_hash`, a `config_hash` jest
sha256 kanonicznego JSON-a **zwalidowanego modelu**, nie bajtow pliku YAML.
Konsekwencje, ktore sa tu celowe:

* przeformatowanie YAML-a nie zmienia hasha,
* zmiana kolejnosci kluczy nie zmienia hasha,
* `configs/env.local.yaml` (HOST_ROLE) jest z hasha wykluczony, wiec laptop
  i klaster licza ten sam hash dla tego samego configu (10_COMPUTE.md §3).

Wartosci liczbowe pochodza z docs/09_DECISIONS.md §6 i sa zamrozone.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.paths import CONFIGS_DIR, ENV_LOCAL_PATH
from src.utils.hashing import sha256_json
from src.utils.io import read_yaml

NormalizerProfile = Literal["strict", "light"]
TaggerBackend = Literal["camel"]
Disambiguator = Literal["mle", "bert"]
HostRole = Literal["laptop", "cluster"]


class _Frozen(BaseModel):
    """Baza: modele sa niemutowalne i odrzucaja nieznane klucze.

    `extra="forbid"` jest tu zabezpieczeniem, nie surowoscia dla samej surowosci:
    literowka w nazwie parametru w YAML-u musialaby inaczej przejsc niezauwazona
    i cicho zostawic wartosc domyslna, a hash i tak by sie zmienil.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class NormalizerCfg(_Frozen):
    profile: NormalizerProfile = "strict"
    version: str = "1.0.0"


class TaggerCfg(_Frozen):
    backend: TaggerBackend = "camel"
    database: str = "calima-msa-r13"
    disambiguator: Disambiguator = "mle"
    version: str = "camel-tools-1.6.0"


class SegmentationCfg(_Frozen):
    window_size: int = 400
    window_size_sensitivity: list[int] = Field(default_factory=lambda: [250, 800])
    overlap: float = 0.0
    overlap_local: float = 0.5
    respect_boundaries: list[str] = Field(default_factory=lambda: ["surah_id", "book_id"])
    min_tail_ratio: float = 0.6
    max_window_ratio: float = 1.6

    @model_validator(mode="after")
    def _check_ratios(self) -> SegmentationCfg:
        if not 0.0 <= self.overlap < 1.0:
            raise ValueError(f"overlap musi byc w [0, 1), dostano {self.overlap}")
        if not 0.0 <= self.overlap_local < 1.0:
            raise ValueError(f"overlap_local musi byc w [0, 1), dostano {self.overlap_local}")
        if self.min_tail_ratio >= self.max_window_ratio:
            raise ValueError("min_tail_ratio musi byc mniejsze niz max_window_ratio")
        return self


class CorpusCfg(_Frozen):
    min_authors: int = 60
    min_tokens_per_author: int = 30000
    min_works_per_author: int = 2
    max_tokens_per_author: int | None = 200000
    death_date_max_ah: int = 900
    near_period_max_ah: int = 500


class VarianceCfg(_Frozen):
    estimators: list[str] = Field(default_factory=lambda: ["med", "disp"])
    n_windows_match: Literal["auto"] | int = "auto"
    # Nazwa `bootstrap_B` lamie snake_case, ale jest dokladnie ta z
    # 09_DECISIONS.md §6. Przemianowanie rozjechaloby config z dokumentacja
    # decyzji, a to cena wyzsza niz jedno odstepstwo stylistyczne.
    bootstrap_B: int = 200  # noqa: N815
    block_unit: str = "author"


class SignificanceCfg(_Frozen):
    permutations: int = 10000
    block_unit_quran: str = "surah_id"
    block_unit_ctrl: str = "author_id"


class FeaturesCfg(_Frozen):
    mfw_grid: list[int] = Field(default_factory=lambda: [100, 300, 1000, 3000])
    char_ngram_range: list[int] = Field(default_factory=lambda: [3, 5])
    char_max_features: int = 50000
    char_min_df: int = 5


class QuotesCfg(_Frozen):
    quote_ngram_n: int = 7
    minhash_num_perm: int = 128
    minhash_threshold: float = 0.8
    match_margin_tokens: int = 3


class AvCfg(_Frozen):
    pairs_max_per_split: int = 400000
    hard_negative_ratio: float = 0.7


class GatesCfg(_Frozen):
    domain_probe_auc_max: float = 0.98
    av_ood_eer_max: float = 0.35


class SplitsCfg(_Frozen):
    ctrl_train: float = 0.60
    ctrl_calib: float = 0.15
    ctrl_test: float = 0.25

    @model_validator(mode="after")
    def _check_sums_to_one(self) -> SplitsCfg:
        total = self.ctrl_train + self.ctrl_calib + self.ctrl_test
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"Udzialy splitow musza sumowac sie do 1.0, dostano {total}")
        return self


class Config(_Frozen):
    """Pelny config projektu. Wszystko, co wchodzi do `config_hash`."""

    seed: int = 20260830
    token_unit: Literal["orthographic_word"] = "orthographic_word"
    normalizer: NormalizerCfg = Field(default_factory=NormalizerCfg)
    tagger: TaggerCfg = Field(default_factory=TaggerCfg)
    segmentation: SegmentationCfg = Field(default_factory=SegmentationCfg)
    corpus: CorpusCfg = Field(default_factory=CorpusCfg)
    variance: VarianceCfg = Field(default_factory=VarianceCfg)
    significance: SignificanceCfg = Field(default_factory=SignificanceCfg)
    features: FeaturesCfg = Field(default_factory=FeaturesCfg)
    quotes: QuotesCfg = Field(default_factory=QuotesCfg)
    av: AvCfg = Field(default_factory=AvCfg)
    gates: GatesCfg = Field(default_factory=GatesCfg)
    splits: SplitsCfg = Field(default_factory=SplitsCfg)
    experiments_skip: list[str] = Field(default_factory=list)

    def hashable_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def config_hash(self) -> str:
        return sha256_json(self.hashable_payload())


class EnvLocal(_Frozen):
    """Warstwa srodowiskowa. Celowo POZA `config_hash` (11_HANDOFF.md §6)."""

    host_role: HostRole = "laptop"


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Scalanie warstwowe base + overlay; overlay wygrywa na poziomie liscia."""
    merged = dict(base)
    for key, value in overlay.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def load_config(
    path: Path | str = CONFIGS_DIR / "base.yaml", *, overlays: list[Path] | None = None
) -> Config:
    """Laduje config bazowy i opcjonalne nakladki, w podanej kolejnosci."""
    payload = read_yaml(Path(path))
    for overlay_path in overlays or []:
        payload = deep_merge(payload, read_yaml(Path(overlay_path)))
    return Config.model_validate(payload)


def load_env_local(path: Path = ENV_LOCAL_PATH) -> EnvLocal:
    """Czyta HOST_ROLE. Brak pliku = `laptop`, bo agent nie ma dostepu do klastra."""
    if not path.exists():
        return EnvLocal()
    return EnvLocal.model_validate(read_yaml(path))
