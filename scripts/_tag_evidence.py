"""Dodatkowe próbki tytułów dla tagów, które wyglądają na dwuznaczne."""

from collections import defaultdict

from src.data.download_openiti import load_metadata


def parse_tags(tagstr: str) -> list[str]:
    return [c.strip() for c in str(tagstr).replace(":::", " ").split() if c.strip()]

WATCH = {
    "_ADAB",
    "_ADHKAR",
    "_AKHLAQ",
    "_BALAGHA",
    "_HADITH",
    "_TARAJIM",
    "_TARIKH",
    "_BULDAN",
    "_CAQAID",
    "_AMALI",
}

df = load_metadata()
samples: dict[str, list[str]] = defaultdict(list)
for row in df.itertuples():
    tags = set(parse_tags(row.tags))
    title = row.title_lat or row.book
    for tag in WATCH:
        if tag in tags and len(samples[tag]) < 8:
            if title and title not in samples[tag]:
                samples[tag].append(title)

from pathlib import Path

lines = []
for tag, titles in samples.items():
    lines.append(tag)
    for t in titles:
        lines.append(f"  - {t}")
Path(r"C:\Users\Kubol\AppData\Local\Temp\tag_evidence2.txt").write_text(
    "\n".join(lines), encoding="utf-8"
)
print("wrote")
