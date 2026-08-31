"""Pobiera teksty z ctrl_manifest.csv i raportuje rozmiar na dysku."""

from __future__ import annotations

import pandas as pd

from src.data.select_ctrl import SELECTED_TEXT_DIR, _download_selected_texts
from src.paths import CTRL_MANIFEST_PATH
from src.utils.io import write_json
from src.paths import RESULTS_DIR


def disk_bytes(dest) -> int:
    if not dest.is_dir():
        return 0
    return sum(p.stat().st_size for p in dest.iterdir() if p.is_file())


def main() -> None:
    books = pd.read_csv(CTRL_MANIFEST_PATH, dtype={"version_uri": str, "local_path": str})
    print(f"manifest authors={books['author_id'].nunique()} books={len(books)}", flush=True)
    report = _download_selected_texts(books, SELECTED_TEXT_DIR, workers=8)
    report["n_bytes_on_disk"] = disk_bytes(SELECTED_TEXT_DIR)
    report["n_files_on_disk"] = sum(1 for p in SELECTED_TEXT_DIR.iterdir() if p.is_file())
    report["n_gib_on_disk"] = round(report["n_bytes_on_disk"] / (1024**3), 3)
    write_json(RESULTS_DIR / "ctrl_download_size.json", report)
    print(report)


if __name__ == "__main__":
    main()
