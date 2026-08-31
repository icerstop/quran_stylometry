"""Rozklad tokenow per autor + symulacja capow (T-015 limit, bez prokowania).

Zrodlo A: total_tokens z manifestu (OpenITI tok_length).
Zrodlo B: tokeny po normalize(strict) na plikach z dysku — ta sama definicja
co 206.8 mln z T-013.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd

from src.data.normalize_arabic import normalize
from src.data.select_ctrl import SELECTED_TEXT_DIR
from src.paths import CTRL_MANIFEST_PATH, RESULTS_DIR
from src.utils.io import write_json

LIMITS = (50_000, 100_000, 150_000, 200_000, 300_000)


def _summarize(author_tokens: dict[str, float], genre: dict[str, str], label: str) -> dict:
    s = pd.Series(author_tokens, dtype=float)
    n = int(len(s))
    caps = {}
    for lim in LIMITS:
        clipped = int((s > lim).sum())
        total = float(s.clip(upper=lim).sum())
        caps[str(lim)] = {
            "limit": lim,
            "corpus_tokens": int(round(total)),
            "n_authors_clipped": clipped,
            "n_authors_uncapped": n - clipped,
        }
    top = s.sort_values(ascending=False).head(10)
    return {
        "source": label,
        "n_authors": n,
        "min": int(s.min()),
        "median": float(s.median()),
        "mean": float(s.mean()),
        "max": int(s.max()),
        "sum": int(s.sum()),
        "top10": [
            {
                "author_id": aid,
                "tokens": int(tok),
                "author_genre": genre.get(aid, ""),
            }
            for aid, tok in top.items()
        ],
        "cap_simulations": caps,
    }


def manifest_author_tokens() -> tuple[dict[str, float], dict[str, str]]:
    m = pd.read_csv(CTRL_MANIFEST_PATH)
    authors = m.drop_duplicates("author_id")
    tokens = dict(zip(authors["author_id"], authors["total_tokens"], strict=True))
    genre = dict(zip(authors["author_id"], authors["author_genre"], strict=True))
    return {str(k): float(v) for k, v in tokens.items()}, {str(k): str(v) for k, v in genre.items()}


def file_author_tokens(genre: dict[str, str]) -> dict[str, float]:
    m = pd.read_csv(CTRL_MANIFEST_PATH, dtype={"version_uri": str})
    uri_to_author = dict(zip(m["version_uri"], m["author_id"].astype(str), strict=True))
    counts: dict[str, float] = defaultdict(float)
    files = sorted(p for p in SELECTED_TEXT_DIR.iterdir() if p.is_file())
    for i, path in enumerate(files, start=1):
        author = uri_to_author.get(path.name)
        if author is None:
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        n = len(normalize(raw, "strict").split())
        counts[author] += n
        if i % 100 == 0:
            print(f"count {i}/{len(files)}", flush=True)
    return dict(counts)


def main() -> None:
    meta_tokens, genre = manifest_author_tokens()
    meta = _summarize(meta_tokens, genre, "openiti_tok_length_manifest")
    print("=== manifest tok_length ===", flush=True)
    print(
        f"n={meta['n_authors']} min={meta['min']} median={meta['median']:.0f} "
        f"mean={meta['mean']:.0f} max={meta['max']} sum={meta['sum']}",
        flush=True,
    )
    for row in meta["top10"]:
        print(f"  {row['tokens']:>12}  {row['author_genre']:<20} {row['author_id']}", flush=True)
    for lim, rec in meta["cap_simulations"].items():
        print(
            f"  cap {lim}: corpus={rec['corpus_tokens']} clipped={rec['n_authors_clipped']}/106",
            flush=True,
        )

    print("=== counting normalized tokens on disk ===", flush=True)
    file_tokens = file_author_tokens(genre)
    files = _summarize(file_tokens, genre, "normalize_strict_whitespace")
    print(
        f"n={files['n_authors']} min={files['min']} median={files['median']:.0f} "
        f"mean={files['mean']:.0f} max={files['max']} sum={files['sum']}",
        flush=True,
    )
    for row in files["top10"]:
        print(f"  {row['tokens']:>12}  {row['author_genre']:<20} {row['author_id']}", flush=True)
    for lim, rec in files["cap_simulations"].items():
        print(
            f"  cap {lim}: corpus={rec['corpus_tokens']} clipped={rec['n_authors_clipped']}/106",
            flush=True,
        )

    write_json(
        RESULTS_DIR / "ctrl_author_token_caps.json",
        {"manifest": meta, "normalized": files},
    )


if __name__ == "__main__":
    main()
