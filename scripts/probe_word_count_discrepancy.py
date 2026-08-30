"""Diagnostyka jednorazowa: rozbieznosc 77429 (EQTB, T-009) vs powszechnie
cytowane "77430" (QAC).

Wynik (2026-08-30): **NIE JEST TO ROZBIEZNOSC W NASZYCH DANYCH.** Publikowana
na stronie `corpus.quran.com` przykladowa tabela Java API
(`Chapter.getTokenCount()`, zrodlo pierwotne QAC, nie trzeciorzedny blog) sumuje
sie do **77429**, identycznie jak nasze dane, i zgadza sie z nami CHAPTER PO
CHAPTER, bez zadnego wyjatku (0/114 roznic). Powszechnie cytowane "77430"
(Wikipedia, blogi) jest wiec nieprecyzyjnym/zaokraglonym cytatem wtornym, nie
autorytatywna liczba samego QAC. Tabela: `src/data/download_qac.py`
(`QAC_JAVA_API_TOKEN_COUNTS`, przepisana 2026-08-30 ze strony
corpus.quran.com/java/example/tokencountexample.jsp).

Nie jest czescia pipeline'u — jak scripts/probe_eqtb_archive.py, to
dochodzenie diagnostyczne uruchamiane recznie, nie wpiete w make/CLI.
"""

from __future__ import annotations

import pandas as pd

from src.data.download_qac import QAC_JAVA_API_TOKEN_COUNTS
from src.paths import REPO_ROOT, RESULTS_DIR


def main() -> None:
    df = pd.read_parquet(REPO_ROOT / "data" / "interim" / "eqtb_tokens.parquet")
    real = df.loc[df["word_id"].astype(str).str.strip() != "0"].copy()
    real["chapter_id_int"] = real["chapter_id"].astype(int)
    real["verse_id_int"] = real["verse_id"].astype(int)
    real["word_id_int"] = real["word_id"].astype(int)

    per_surah = real.groupby("chapter_id_int").apply(
        lambda g: g[["verse_id_int", "word_id_int"]].drop_duplicates().shape[0],
        include_groups=False,
    )

    reference = pd.Series(QAC_JAVA_API_TOKEN_COUNTS, name="qac_reference")
    comparison = pd.DataFrame({"eqtb": per_surah, "qac_reference": reference})
    comparison["diff"] = comparison["eqtb"] - comparison["qac_reference"]

    out_path = RESULTS_DIR / "eqtb_vs_qac_per_surah.csv"
    comparison.to_csv(out_path, index_label="chapter_id")

    n_diff = int((comparison["diff"] != 0).sum())
    print(f"zapisano {out_path}")
    print(f"EQTB total:          {int(per_surah.sum())}")
    print(f"QAC reference total: {int(reference.sum())}")
    print(f"chapters differing:  {n_diff} / 114")
    if n_diff:
        print(comparison.loc[comparison["diff"] != 0])
    else:
        print("ZGODNOSC PELNA: 0/114 sur roznych miedzy EQTB i QAC (Java API).")


if __name__ == "__main__":
    main()
