"""Jeden normalizator arabskiego (G2) — docs/03_DATA.md §4, T-013.

Stosowany identycznie do Koranu (imlaai_token z EQTB) i do CTRL.
Profile: `strict` (wszystkie kroki) i `light` (bez pkt. 5–6).

Kolejnosc jest czescia decyzji, nie szczegolem implementacji:

  0. mARkdown OpenITI — EMPIRIA T-013: 10/10 plikow z data/raw/openiti/selected
     nadal ma #META#, PageV, ~~, msNN. T-011 liczylo quality_proxy.strip_markdwn
     w pamieci i wyrzucalo tekst; na dysku markup zostal. Wiec krok 0 jest
     konieczny; nie jest duplikatem zapisu T-011.
  1. Unicode NFC.
  2. Tatweel U+0640.
  3. Znaki pauzy koranicznej, koniec ajatu, sajda, ozdobniki.
  4. Diakrytyki (harakat, shadda, sukun, alif khanjariyya) — OBA profile
     (03_DATA §4: light = bez pkt. 5–6, nie bez pkt. 4; configs/normalizer.yaml).
  5–6. Tylko strict: alify, ى→ي, ة→ه, ؤ→و, ئ→ي, ءا→ا
     (ءا = EQTB imlaai dla maddy/hamzy początkowej, ten sam fonem co آ).
  7. Znaki spoza blokow arabskich + biale znaki.

Dlaczego 4 PRZED 5: znaki laczace (U+064B–U+065F, U+0670) musza zejsc zanim
zlozymy warianty alifu do ا. W przeciwnym razie resztkowy combining mark
przykleja sie do juz ujednoliconego ا, NFC daje inna sekwencje i
normalize(normalize(x)) != normalize(x). Hamza w أ/إ/آ to litera prekomponowana
(nie diakrytyk) — schodzi dopiero w kroku 5; odwrotna kolejnosc tez zlozy alif,
ale psuje idempotencje przy sztylecie alifu i wasli laczacej.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from src.data.quality_proxy import strip_markdwn

NormalizerProfile = Literal["strict", "light"]

# Krok 2.
_TATWEEL = "\u0640"

# Krok 3: pauza / ajaty / sajda / ozdobniki (nie harakat — te sa w kroku 4).
_QURANIC_ORNAMENT = re.compile(
    r"["
    r"\u06D6-\u06ED"  # small high quranic marks + end of ayah 06DD
    r"\u06DE"  # start of rub el hizb
    r"\u06E9"  # place of sajdah
    r"\u08D3-\u08FF"  # arabic extended marks
    r"\uFDF0-\uFDFD"  # honorific ligatures ﷺ ﷻ ﷽
    r"\u0615-\u061A"
    r"\u0610-\u0614"
    r"]+"
)

# Krok 4.
_DIACRITICS = re.compile(
    r"["
    r"\u064B-\u065F"  # fatha..sukun, shadda, hamza above/below as marks
    r"\u0670"  # dagger alif
    r"]+"
)

# Krok 5–6 (strict).
_ALIF_VARIANTS = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ة": "ه",
        "ؤ": "و",
        "ئ": "ي",
    }
)
# EQTB imlaai zapisuje maddę/hamzę początkową jako ء+ا (U+0621, U+0627),
# nie jako prekomponowane آ (U+0622). OpenITI/Shamela ma آ lub ا.
# Bez tego kroku ءامنوا (Q33:56) != امنوا (CTRL) przy identycznym normalize().
_HAMZA_ALEF = "ءا"

# Krok 7: pozostaw bloki arabskie + biale znaki (jeden sub, nie per-znak).
_NON_ARABIC = re.compile(
    r"[^\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF\s]+"
)
_WHITESPACE = re.compile(r"\s+")

# Ligatury prezentacyjne bez honorificow FDF0–FDFD (te schodza w kroku 3).
_PRES_FORM = re.compile(r"[\uFB50-\uFDEF\uFE70-\uFEFF]")


def _decompose_presentation_forms(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return unicodedata.normalize("NFKC", match.group(0))

    return _PRES_FORM.sub(repl, text)


def _strip_openiti_markdown(text: str) -> str:
    """Krok 0. Reuzywa T-011 strip_markdwn + ~~ widoczne w probce T-013."""
    cleaned, _n = strip_markdwn(text)
    return cleaned.replace("~~", "")


def strip_diacritics_and_ligatures(text: str) -> str:
    """Wariant kontrolny F1: ligatury NFKC + harakat na juz znormalizowanym tekscie."""
    out = unicodedata.normalize("NFKC", text)
    out = _decompose_presentation_forms(out)
    out = _DIACRITICS.sub("", out)
    return _WHITESPACE.sub(" ", out).strip()


def normalize(text: str, profile: NormalizerProfile = "strict") -> str:
    """Normalizuje lancuch (token albo pasaz). Wejscie: imlaai / OpenITI."""
    if profile not in {"strict", "light"}:
        raise ValueError(f"Nieznany profil normalizatora: {profile!r}")

    # 0 — markup na dysku (empiria T-013, results/t013_markdown_probe.json)
    out = _strip_openiti_markdown(text)
    # 1
    out = unicodedata.normalize("NFC", out)
    # 2
    out = out.replace(_TATWEEL, "")
    # 3 — ozdobniki / pauza PRZED rozbiciem ligatur, zeby ﷺ nie puchlo do wielu slow
    out = _QURANIC_ORNAMENT.sub("", out)
    out = _decompose_presentation_forms(out)
    # 4 — oba profile
    out = _DIACRITICS.sub("", out)
    # 5–6 — tylko strict
    if profile == "strict":
        out = out.translate(_ALIF_VARIANTS)
        out = out.replace(_HAMZA_ALEF, "ا")
    # 7
    out = _NON_ARABIC.sub("", out)
    out = _WHITESPACE.sub(" ", out).strip()
    return out


def normalize_tokens(
    tokens: Sequence[str],
    profile: NormalizerProfile = "strict",
) -> list[str]:
    """Ta sama liczba pozycji. Nie wyrzuca tokenow z listy (03_DATA §4)."""
    return [normalize(tok, profile) for tok in tokens]


def token_count(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    return len(stripped.split())


def benchmark_ctrl(files: Sequence[Path]) -> dict[str, object]:
    """Normalizuje pliki CTRL na poziomie pasazu (jeden przebieg na plik).

    Liczba tokenow: split po kroku 0 vs split po pelnym normalize.
    Lista tokenow (normalize_tokens) jest testowana jednostkowo — tu byloby
    zbyt wolne na 2 GB (miliony wywolan Pythona).
    """
    import time

    n_files = 0
    n_bytes = 0
    n_tok_before = 0
    n_tok_after_strict = 0
    n_tok_after_light = 0
    n_empty_sample = 0
    n_sample = 0
    sampled = False
    t0 = time.perf_counter()
    t_strict = 0.0
    t_light = 0.0
    for path in files:
        raw = Path(path).read_text(encoding="utf-8", errors="replace")
        n_bytes += len(raw.encode("utf-8"))
        n_files += 1
        after_markup = _strip_openiti_markdown(raw)
        tokens_before = after_markup.split()
        n_tok_before += len(tokens_before)
        ts = time.perf_counter()
        strict_txt = normalize(raw, "strict")
        t_strict += time.perf_counter() - ts
        n_tok_after_strict += token_count(strict_txt)
        tl = time.perf_counter()
        light_txt = normalize(raw, "light")
        t_light += time.perf_counter() - tl
        n_tok_after_light += token_count(light_txt)
        if not sampled and tokens_before:
            sample = tokens_before[:5000]
            n_sample = len(sample)
            n_empty_sample = sum(1 for tok in normalize_tokens(sample, "strict") if tok == "")
            sampled = True
        if n_files % 100 == 0:
            print(f"normalize {n_files}/{len(files)}", flush=True)
    elapsed = time.perf_counter() - t0
    return {
        "n_files": n_files,
        "n_bytes": n_bytes,
        "n_tokens_before": n_tok_before,
        "n_tokens_after_strict": n_tok_after_strict,
        "n_tokens_after_light": n_tok_after_light,
        "elapsed_sec_total": round(elapsed, 3),
        "elapsed_sec_strict": round(t_strict, 3),
        "elapsed_sec_light": round(t_light, 3),
        "under_5_min": elapsed < 300,
        "token_list_sample_n": n_sample,
        "token_list_sample_empty": n_empty_sample,
    }
