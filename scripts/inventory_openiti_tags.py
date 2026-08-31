"""Jednorazowy inwentarz tagow OpenITI z przykladami tytulow (T-011 / §4)."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from src.data.download_openiti import load_metadata
from src.paths import RESULTS_DIR
from src.utils.io import write_json


def parse_tags(tagstr: str) -> list[str]:
    parts: list[str] = []
    for chunk in str(tagstr).replace(":::", " ").split():
        token = chunk.strip()
        if token and token not in {":", "-", "|", ":::"}:
            parts.append(token)
    return parts


def main() -> None:
    df = load_metadata()
    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    prefixes: Counter[str] = Counter()

    for row in df.itertuples():
        title = (row.title_lat or row.book or "")[:90]
        for tag in parse_tags(row.tags):
            counts[tag] += 1
            if tag.startswith("_"):
                prefixes["_UNDERSCORE"] += 1
            elif tag.startswith("GAL@"):
                prefixes["GAL@"] += 1
            elif "@" in tag:
                prefixes[tag.split("@", 1)[0] + "@"] += 1
            else:
                prefixes["PLAIN"] += 1
            if title and len(examples[tag]) < 5:
                examples[tag].append(title)

    inventory = {
        "n_unique_tags": len(counts),
        "prefix_counts": dict(prefixes),
        "underscore_tags": {
            tag: {"n": n, "evidence_sample": examples[tag]}
            for tag, n in sorted(counts.items(), key=lambda kv: -kv[1])
            if tag.startswith("_")
        },
        "gal_tags_n_ge_20": {
            tag: {"n": n, "evidence_sample": examples[tag]}
            for tag, n in sorted(counts.items(), key=lambda kv: -kv[1])
            if tag.startswith("GAL@") and n >= 20
        },
        "plain_tags_n_ge_30": {
            tag: {"n": n, "evidence_sample": examples[tag]}
            for tag, n in sorted(counts.items(), key=lambda kv: -kv[1])
            if not tag.startswith("_")
            and not tag.startswith("GAL@")
            and "@" not in tag
            and tag not in {"PRIMARY_VERSION", "CLEANED_VERSION"}
            and n >= 30
        },
    }
    write_json(RESULTS_DIR / "openiti_tag_inventory.json", inventory)
    print(f"unique_tags={len(counts)}")
    print(f"underscore={sum(1 for t in counts if t.startswith('_'))}")
    print(f"wrote results/openiti_tag_inventory.json")


if __name__ == "__main__":
    main()
