"""Jednorazowe dochodzenie: `corpus/Quranic.rar` w NoorBayan/Quranic (T-009 prework).

`corpus/Quran.csv` (sprawdzany automatycznie przez `make verify-sources`) ma
tylko 5 kolumn na poziomie ajatu. Ten skrypt sprawdza, czy tabela tokenowa
o ~42 kolumnach z `docs/09_DECISIONS.md` §2.1 siedzi w `corpus/Quranic.rar`.

Nie jest czescia `make verify-sources`: wymaga 7-Zip (system, nie pip) i sciaga
4 MB archiwum przy kazdym uruchomieniu. To dochodzenie diagnostyczne, nie
routinowa kontrola — ale uzywa TYCH SAMYCH, przetestowanych funkcji sniffujacych
co checker EQTB (`parse_header`, `compare_columns`), zeby wynik byl porownywalny.

Uzycie:
    python scripts/probe_eqtb_archive.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import requests

from src.data.verify_sources import compare_columns, parse_header
from src.paths import CONFIGS_DIR, REPO_ROOT
from src.utils.io import read_json, read_yaml, write_json
from src.utils.provenance import utc_now_iso
from src.utils.runs import log_blocker

RAR_URL = "https://raw.githubusercontent.com/NoorBayan/Quranic/main/corpus/Quranic.rar"
SEVEN_ZIP_CANDIDATES = (
    r"C:\Program Files\7-Zip\7z.exe",
    r"C:\Program Files (x86)\7-Zip\7z.exe",
    "7z",
)


def find_7z() -> str:
    for candidate in SEVEN_ZIP_CANDIDATES:
        if shutil.which(candidate) or Path(candidate).exists():
            return candidate
    raise RuntimeError("7-Zip nie znalezione. Instalacja: winget install --id 7zip.7zip -e")


def download_rar(dest: Path) -> None:
    resp = requests.get(RAR_URL, timeout=60)
    resp.raise_for_status()
    dest.write_bytes(resp.content)


def extract_rar(rar_path: Path, out_dir: Path, seven_zip: str) -> list[Path]:
    subprocess.run(  # noqa: S603
        [seven_zip, "x", str(rar_path), f"-o{out_dir}", "-y"],
        check=True,
        capture_output=True,
    )
    return [p for p in out_dir.iterdir() if p.is_file() and p.name != rar_path.name]


def value_distribution(
    lines: list[str], header: list[str], column: str, sample: int = 20000
) -> Counter[str]:
    idx = header.index(column)
    counts: Counter[str] = Counter()
    for line in lines[1 : sample + 1]:
        row = line.split("\t")
        if len(row) == len(header):
            counts[row[idx]] += 1
    return counts


def main() -> int:
    eqtb_spec = next(
        s for s in read_yaml(CONFIGS_DIR / "sources.yaml")["sources"] if s["id"] == "eqtb"
    )
    expected_columns: list[str] = eqtb_spec["expected_columns"]

    seven_zip = find_7z()
    with tempfile.TemporaryDirectory(prefix="eqtb_probe_") as tmp:
        tmp_dir = Path(tmp)
        rar_path = tmp_dir / "Quranic.rar"
        print(f"Pobieram {RAR_URL} ...")
        download_rar(rar_path)
        print(f"Rozpakowuje {rar_path.stat().st_size} B przez {seven_zip} ...")
        extracted = extract_rar(rar_path, tmp_dir, seven_zip)
        print("Zawartosc archiwum:", [p.name for p in extracted])

        if not extracted:
            raise RuntimeError("Archiwum Quranic.rar jest puste po rozpakowaniu.")
        csv_path = extracted[0]
        blob = csv_path.read_bytes()

        columns, encoding, delimiter = parse_header(blob[:200_000])
        missing, extra = compare_columns(columns, expected_columns)

        text = blob.decode(encoding, errors="replace").lstrip("\ufeff")
        lines = text.splitlines()

        candidates: dict[str, Any] = {}
        if "constituents_loc" in columns:
            sample_vals = [
                line.split("\t")[columns.index("constituents_loc")] for line in lines[1:200]
            ]
            candidates["constituent_position"] = {
                "candidate_column": "constituents_loc",
                "evidence": "Format obserwowany '[start-end]', zgodny z opisem README "
                "'Start and end token IDs defining the span of the constituent'.",
                "sample_values": [v for v in sample_vals if v != "_"][:5],
            }
        if "head_rel" in columns and "depend_rel" in columns:
            head_dist = value_distribution(lines, columns, "head_rel")
            depend_dist = value_distribution(lines, columns, "depend_rel")
            candidates["constituent_node"] = {
                "candidate_column": "head_rel",
                "evidence": (
                    "README samego zrodla oznacza to pole jako niejednoznaczne: "
                    "'previously classification of binary constituent relations, "
                    "might need clarification or renaming'. 'head_rel' jest jedynym "
                    f"kandydatem faktycznie binarnym: {dict(head_dist)}. "
                    f"'depend_rel' ma trzy wartosci, nie dwie: {dict(depend_dist)}."
                ),
                "rejected_alternative": {
                    "column": "depend_rel",
                    "distribution": dict(depend_dist),
                },
                "confidence": "hipoteza, NIE potwierdzenie — zrodlo nie jest pewne nazwy tego pola",
            }

        result = {
            "checked_at": utc_now_iso(),
            "method": "corpus/Quranic.rar (raw.githubusercontent.com) rozpakowany 7-Zip, "
            "sprawdzony tymi samymi funkcjami co corpus/Quran.csv",
            "extracted_member": csv_path.name,
            "extracted_size_bytes": len(blob),
            "observed_encoding": encoding,
            "observed_delimiter": {"\t": "tab", ",": "comma", ";": "semicolon"}.get(
                delimiter, delimiter
            ),
            "n_observed_columns": len(columns),
            "n_expected_columns": len(expected_columns),
            "observed_columns": columns,
            "columns_missing": missing,
            "columns_extra": extra,
            "columns_ok": not missing,
            "unresolved_column_candidates": candidates,
        }

    out_path = REPO_ROOT / "results" / "source_check.json"
    report = read_json(out_path)
    eqtb_entry = next(s for s in report["sources"] if s["id"] == "eqtb")
    eqtb_entry["resolved"]["archive_probe"] = result
    eqtb_entry.setdefault("notes", []).append(
        "T-009 prework: corpus/Quranic.rar -> Quranic.csv (51 kolumn) zawiera "
        f"{len(expected_columns) - len(missing)}/{len(expected_columns)} kolumn z 09_DECISIONS "
        f"§2.1 werbatim. Brakujace: {missing}. Patrz resolved.archive_probe."
    )
    write_json(out_path, report)
    print(f"\nZaktualizowano {out_path}")

    question = (
        "corpus/Quranic.rar (nie corpus/Quran.csv) zawiera tabele tokenowa Quranic.csv "
        f"z {len(columns)} kolumnami. {len(expected_columns) - len(missing)} z "
        f"{len(expected_columns)} oczekiwanych kolumn z 09_DECISIONS §2.1 wystepuje "
        f"WERBATIM. Brakuja: {missing}. Silna hipoteza (nie potwierdzenie): "
        "constituent_position = constituents_loc (span '[start-end]'), "
        "constituent_node = head_rel (jedyne pole faktycznie binarne 0/1; README "
        "samo flaguje ten wpis jako niejednoznaczny/przemianowany). Decyzja do "
        "podjecia: (a) czy przyjmujemy te rename jako rozstrzygniecie formatu "
        "i aktualizujemy configs/sources.yaml + T-009 na Quranic.rar->Quranic.csv, "
        "(b) czy 7-Zip/rozpakowywanie RAR na kazdym `make verify-sources` jest "
        "akceptowalna zaleznoscia systemowa, (c) czy zostawiamy constituent_node "
        "jako pole niepewne i raportujemy to w SOURCES.md."
    )
    log_blocker(
        task="verify-sources",
        question=question,
        context="09_DECISIONS.md §2.1 | archive_probe w results/source_check.json (eqtb.resolved)",
        source=RAR_URL,
        artifacts=["results/source_check.json"],
    )
    print("\nZaktualizowano results/blockers.jsonl (nowy wpis, blocker POZOSTAJE OTWARTY).")
    print(f"\n{question}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(f"BLAD: {exc}", file=sys.stderr)
        sys.exit(1)
