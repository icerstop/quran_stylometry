"""Baseline stylometry for the Quran (Hafs, verse-level corpus)."""

from __future__ import annotations

import csv
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "quran_arabic_structured" / "quran_dataset.csv"
OUT_JSON = ROOT / "data" / "stylometry_baseline.json"

TASHKEEL = re.compile(r"[\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
NON_LETTERS = re.compile(r"[^\u0621-\u063A\u0641-\u064A\u0671\u067E\u0686\u0698\u06A4\u06AF\s]")

# Style-bearing closed-class items (surface forms after tashkeel strip).
# Forms after tashkeel strip + alef/ya folding (على→علي, يا أيها→يايها).
PARTICLES = [
    "من",
    "في",
    "علي",
    "الي",
    "عن",
    "ان",
    "اذا",
    "قد",
    "لم",
    "لن",
    "لا",
    "ما",
    "هل",
    "ثم",
    "او",
    "بل",
    "حتى",
    "الذي",
    "الذين",
    "التي",
    "قال",
    "قالوا",
    "الله",
    "يايها",
]


def strip_tashkeel(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = TASHKEEL.sub("", text)
    text = text.replace("ٱ", "ا").replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي").replace("ة", "ه")
    text = NON_LETTERS.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str) -> list[str]:
    t = strip_tashkeel(text)
    return [w for w in t.split() if w]


def last_letter(text: str) -> str:
    t = strip_tashkeel(text).replace(" ", "")
    return t[-1] if t else ""


def hapax_ratio(toks: list[str]) -> float:
    if not toks:
        return 0.0
    c = Counter(toks)
    return sum(1 for v in c.values() if v == 1) / len(c)


def guiraud(toks: list[str]) -> float:
    if not toks:
        return 0.0
    return len(set(toks)) / math.sqrt(len(toks))


def ttr(toks: list[str]) -> float:
    if not toks:
        return 0.0
    return len(set(toks)) / len(toks)


def mean_word_len(toks: list[str]) -> float:
    if not toks:
        return 0.0
    return sum(len(w) for w in toks) / len(toks)


def particle_rates(toks: list[str], per: int = 1000) -> dict[str, float]:
    n = max(len(toks), 1)
    c = Counter(toks)
    out = {}
    for p in PARTICLES:
        out[p] = 1000.0 * c.get(p, 0) / n
    # attached waw / fa are prefixes; count starts-with
    out["و_prefix"] = 1000.0 * sum(1 for w in toks if w.startswith("و") and w != "و") / n
    out["ف_prefix"] = 1000.0 * sum(1 for w in toks if w.startswith("ف") and len(w) > 1) / n
    return out


def load_verses() -> list[dict]:
    rows = []
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(
                {
                    "surah": int(r["surah_number"]),
                    "ayah": int(r["ayah_number_in_surah"]),
                    "name_en": r["surah_name_en"],
                    "name_ar": r["surah_name_ar"],
                    "period": "Meccan" if r["revelation_type"].startswith("Mecc") else "Medinan",
                    "text": r["text_arabic"],
                }
            )
    return rows


def mannwhitney_u(a: np.ndarray, b: np.ndarray) -> float:
    """Two-sided p-value via normal approximation with tie correction."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n1, n2 = len(a), len(b)
    ranks = np.empty(n1 + n2, dtype=float)
    combined = np.concatenate([a, b])
    order = np.argsort(combined, kind="mergesort")
    sorted_c = combined[order]
    i = 0
    while i < len(sorted_c):
        j = i
        while j < len(sorted_c) and sorted_c[j] == sorted_c[i]:
            j += 1
        avg = (i + j - 1) / 2.0 + 1.0
        ranks[order[i:j]] = avg
        i = j
    r1 = ranks[:n1].sum()
    u1 = r1 - n1 * (n1 + 1) / 2.0
    u2 = n1 * n2 - u1
    u = min(u1, u2)
    mu = n1 * n2 / 2.0
    # tie correction
    _, counts = np.unique(combined, return_counts=True)
    tie = (counts**3 - counts).sum() / 12.0
    var = n1 * n2 * (n1 + n2 + 1) / 12.0 - n1 * n2 * tie / ((n1 + n2) * (n1 + n2 - 1))
    if var <= 0:
        return 1.0
    z = (u - mu + 0.5) / math.sqrt(var)  # continuity
    # two-sided from normal cdf
    p = math.erfc(abs(z) / math.sqrt(2.0))
    return float(p)


def cliffs_delta(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a)
    b = np.asarray(b)
    # efficient pairwise via broadcasting for modest n
    gt = np.sum(a[:, None] > b[None, :])
    lt = np.sum(a[:, None] < b[None, :])
    return float((gt - lt) / (len(a) * len(b)))


def main() -> None:
    verses = load_verses()
    by_surah: dict[int, list[dict]] = defaultdict(list)
    for v in verses:
        by_surah[v["surah"]].append(v)

    surah_rows = []
    all_meccan_toks: list[str] = []
    all_medinan_toks: list[str] = []
    rhyme_period: dict[str, Counter] = {"Meccan": Counter(), "Medinan": Counter()}
    ayah_len_period: dict[str, list[int]] = {"Meccan": [], "Medinan": []}

    for sid in sorted(by_surah):
        vs = by_surah[sid]
        period = vs[0]["period"]
        toks: list[str] = []
        ayah_lens = []
        rhymes = Counter()
        for v in vs:
            t = tokens(v["text"])
            toks.extend(t)
            ayah_lens.append(len(t))
            rhymes[last_letter(v["text"])] += 1
            rhyme_period[period][last_letter(v["text"])] += 1
            ayah_len_period[period].append(len(t))
        if period == "Meccan":
            all_meccan_toks.extend(toks)
        else:
            all_medinan_toks.extend(toks)
        rates = particle_rates(toks)
        surah_rows.append(
            {
                "surah": sid,
                "name": vs[0]["name_en"],
                "name_ar": vs[0]["name_ar"],
                "period": period,
                "n_ayah": len(vs),
                "n_tokens": len(toks),
                "mean_ayah_len": round(float(np.mean(ayah_lens)), 3),
                "median_ayah_len": round(float(np.median(ayah_lens)), 3),
                "mean_word_len": round(mean_word_len(toks), 3),
                "ttr": round(ttr(toks), 4),
                "hapax_ratio": round(hapax_ratio(toks), 4),
                "guiraud": round(guiraud(toks), 4),
                "top_rhyme": rhymes.most_common(1)[0][0] if rhymes else "",
                "rhyme_share": round(rhymes.most_common(1)[0][1] / len(vs), 4) if rhymes else 0,
                "rates": {k: round(v, 3) for k, v in rates.items()},
            }
        )

    # Function-word matrix for PCA (length-normalized rates)
    feat_keys = [
        "من",
        "في",
        "علي",
        "الي",
        "ان",
        "قد",
        "لم",
        "لا",
        "ما",
        "ثم",
        "الذي",
        "الذين",
        "قال",
        "قالوا",
        "الله",
        "يايها",
        "و_prefix",
        "ف_prefix",
    ]
    X = np.array([[s["rates"].get(k, 0.0) for k in feat_keys] for s in surah_rows], dtype=float)
    Xs = StandardScaler().fit_transform(X)
    pca = PCA(n_components=2, random_state=0)
    coords = pca.fit_transform(Xs)
    for s, (x, y) in zip(surah_rows, coords):
        s["pc1"] = round(float(x), 4)
        s["pc2"] = round(float(y), 4)

    meccan = [s for s in surah_rows if s["period"] == "Meccan"]
    medinan = [s for s in surah_rows if s["period"] == "Medinan"]

    def arr(rows, key):
        return np.array([r[key] for r in rows], dtype=float)

    comparisons = []
    for key, label in [
        ("mean_ayah_len", "Średnia długość ajatu (tokeny)"),
        ("mean_word_len", "Średnia długość słowa (litery)"),
        ("guiraud", "Bogactwo leksykalne (Guiraud R)"),
        ("hapax_ratio", "Udział hapax legomena"),
        ("n_ayah", "Liczba ajatów w surze"),
        ("n_tokens", "Liczba tokenów w surze"),
    ]:
        a, b = arr(meccan, key), arr(medinan, key)
        comparisons.append(
            {
                "metric": key,
                "label": label,
                "meccan_mean": round(float(a.mean()), 3),
                "medinan_mean": round(float(b.mean()), 3),
                "meccan_median": round(float(np.median(a)), 3),
                "medinan_median": round(float(np.median(b)), 3),
                "p_mannwhitney": round(mannwhitney_u(a, b), 6),
                "cliffs_delta": round(cliffs_delta(a, b), 3),
            }
        )

    # particle rate comparisons at surah level
    particle_cmp = []
    for k in feat_keys:
        a = np.array([s["rates"][k] for s in meccan])
        b = np.array([s["rates"][k] for s in medinan])
        particle_cmp.append(
            {
                "particle": k,
                "meccan_per_1000": round(float(a.mean()), 2),
                "medinan_per_1000": round(float(b.mean()), 2),
                "p_mannwhitney": round(mannwhitney_u(a, b), 6),
                "cliffs_delta": round(cliffs_delta(a, b), 3),
            }
        )
    particle_cmp.sort(key=lambda d: abs(d["cliffs_delta"]), reverse=True)

    def corpus_stats(toks: list[str], verses_n: int) -> dict:
        return {
            "tokens": len(toks),
            "types": len(set(toks)),
            "ttr": round(ttr(toks), 4),
            "hapax_ratio": round(hapax_ratio(toks), 4),
            "guiraud": round(guiraud(toks), 4),
            "mean_word_len": round(mean_word_len(toks), 3),
            "verses": verses_n,
        }

    n_mecc_v = sum(1 for v in verses if v["period"] == "Meccan")
    n_med_v = sum(1 for v in verses if v["period"] == "Medinan")

    def rhyme_share(counter: Counter, n: int, k=8):
        return [
            {"letter": let, "share": round(cnt / n, 4), "count": cnt}
            for let, cnt in counter.most_common(k)
        ]

    # length bins for ayah tokens
    def hist(vals, edges):
        counts = []
        labels = []
        for i in range(len(edges) - 1):
            lo, hi = edges[i], edges[i + 1]
            counts.append(int(((np.array(vals) >= lo) & (np.array(vals) < hi)).sum()))
            labels.append(f"{lo}–{hi - 1}" if hi - lo > 1 else str(lo))
        counts.append(int((np.array(vals) >= edges[-1]).sum()))
        labels.append(f"{edges[-1]}+")
        return labels, counts

    edges = [1, 3, 6, 11, 21, 41]
    lab, c_m = hist(ayah_len_period["Meccan"], edges)
    _, c_d = hist(ayah_len_period["Medinan"], edges)
    # normalize to percent
    def pct(c):
        s = sum(c) or 1
        return [round(100.0 * x / s, 1) for x in c]

    # outliers: longest mean ayah, richest Guiraud among surahs with >= 50 tokens
    longish = [s for s in surah_rows if s["n_tokens"] >= 50]
    longest = sorted(surah_rows, key=lambda s: s["mean_ayah_len"], reverse=True)[:8]
    shortest = sorted(surah_rows, key=lambda s: s["mean_ayah_len"])[:8]
    richest = sorted(longish, key=lambda s: s["guiraud"], reverse=True)[:8]
    poorest = sorted(longish, key=lambda s: s["guiraud"])[:8]

    # Burrows-like centroid distance in scaled particle space
    mecc_idx = [i for i, s in enumerate(surah_rows) if s["period"] == "Meccan"]
    med_idx = [i for i, s in enumerate(surah_rows) if s["period"] == "Medinan"]
    c_m_vec = Xs[mecc_idx].mean(axis=0)
    c_d_vec = Xs[med_idx].mean(axis=0)
    dist = float(np.linalg.norm(c_m_vec - c_d_vec))
    # leave-one-out nearest centroid accuracy
    correct = 0
    for i, s in enumerate(surah_rows):
        rest_m = [j for j in mecc_idx if j != i]
        rest_d = [j for j in med_idx if j != i]
        cm = Xs[rest_m].mean(axis=0)
        cd = Xs[rest_d].mean(axis=0)
        pred = "Meccan" if np.linalg.norm(Xs[i] - cm) < np.linalg.norm(Xs[i] - cd) else "Medinan"
        if pred == s["period"]:
            correct += 1
    acc = correct / len(surah_rows)

    # distinctive words: log-odds with dirichlet prior
    cm_c = Counter(all_meccan_toks)
    dm_c = Counter(all_medinan_toks)
    vocab = set(cm_c) | set(dm_c)
    a0, b0 = 0.01, 0.01
    n_m, n_d = len(all_meccan_toks), len(all_medinan_toks)
    scored = []
    for w in vocab:
        if cm_c[w] + dm_c[w] < 30:
            continue
        if len(w) < 2:
            continue
        p_m = (cm_c[w] + a0) / (n_m + a0 * len(vocab))
        p_d = (dm_c[w] + b0) / (n_d + b0 * len(vocab))
        lod = math.log(p_m) - math.log(p_d)
        scored.append((lod, w, cm_c[w], dm_c[w]))
    scored.sort()
    medinan_words = [
        {"word": w, "log_odds": round(-lod, 3), "meccan": mc, "medinan": dc}
        for lod, w, mc, dc in scored[:12]
    ]
    meccan_words = [
        {"word": w, "log_odds": round(lod, 3), "meccan": mc, "medinan": dc}
        for lod, w, mc, dc in scored[-12:][::-1]
    ]

    payload = {
        "source": "treamyracle/quran-arabic-english-dataset (Hafs Arabic text)",
        "normalization": "tashkeel stripped; alef/ya/ta-marbuta folded for tokens",
        "n_verses": len(verses),
        "n_surahs": len(surah_rows),
        "n_meccan_surahs": len(meccan),
        "n_medinan_surahs": len(medinan),
        "corpus": {
            "Meccan": corpus_stats(all_meccan_toks, n_mecc_v),
            "Medinan": corpus_stats(all_medinan_toks, n_med_v),
            "All": corpus_stats(all_meccan_toks + all_medinan_toks, len(verses)),
        },
        "comparisons": comparisons,
        "particles": particle_cmp,
        "pca_variance": [round(float(x), 4) for x in pca.explained_variance_ratio_],
        "centroid_distance": round(dist, 3),
        "nearest_centroid_accuracy": round(acc, 3),
        "ayah_len_hist": {
            "bins": lab,
            "meccan_pct": pct(c_m),
            "medinan_pct": pct(c_d),
        },
        "rhyme": {
            "Meccan": rhyme_share(rhyme_period["Meccan"], n_mecc_v),
            "Medinan": rhyme_share(rhyme_period["Medinan"], n_med_v),
        },
        "distinctive_words": {"Meccan": meccan_words, "Medinan": medinan_words},
        "longest_ayah_surahs": [
            {k: s[k] for k in ("surah", "name", "period", "mean_ayah_len", "n_ayah")}
            for s in longest
        ],
        "shortest_ayah_surahs": [
            {k: s[k] for k in ("surah", "name", "period", "mean_ayah_len", "n_ayah")}
            for s in shortest
        ],
        "richest_surahs": [
            {k: s[k] for k in ("surah", "name", "period", "guiraud", "n_tokens")}
            for s in richest
        ],
        "poorest_surahs": [
            {k: s[k] for k in ("surah", "name", "period", "guiraud", "n_tokens")}
            for s in poorest
        ],
        "surahs": surah_rows,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {k: payload[k] for k in payload if k not in ("surahs", "distinctive_words", "rhyme")}
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    print("WROTE", str(OUT_JSON))


if __name__ == "__main__":
    main()
