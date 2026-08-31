import json
from pathlib import Path

inv = json.loads(Path("results/openiti_tag_inventory.json").read_text(encoding="utf-8"))
lines = ["UNDERSCORE TAGS"]
for tag, rec in sorted(inv["underscore_tags"].items(), key=lambda kv: -kv[1]["n"]):
    samples = " | ".join(rec["evidence_sample"][:3])
    lines.append(f"{rec['n']:5} {tag}")
    lines.append(f"      {samples}")
Path(r"C:\Users\Kubol\AppData\Local\Temp\underscore_tags.txt").write_text(
    "\n".join(lines), encoding="utf-8"
)
print("n", len(inv["underscore_tags"]))
