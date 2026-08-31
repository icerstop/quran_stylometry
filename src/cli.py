"""Punkt wejscia CLI. Cala warstwa stanu zyje tutaj; `src/` ponizej jest czysty.

Kazdy target z Makefile'a woła dokladnie jedna podkomende tego modulu — dzieki
temu recipe sa przenosne miedzy /bin/sh a cmd.exe.

Etapy jeszcze niezaimplementowane (P1..P6) NIE sa cichymi no-opami: koncza sie
kodem 2 i komunikatem wskazujacym zadanie z docs/07_TASKS.md. Cichy sukces
pustego etapu jest gorszy niz jawna porazka.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from src.config import Config, load_config
from src.paths import (
    CHARACTER_REPORT_PATH,
    CHRONOLOGY_AGREEMENT_PATH,
    FUNCTION_REPORT_PATH,
    LEXICAL_REPORT_PATH,
    CONFIGS_DIR,
    ENV_LOCAL_PATH,
    FROZEN_CONFIG_DIR,
    INTERNAL_DUP_PATH,
    RESULTS_DIR,
    SEGMENTATION_REPORT_PATH,
    SPLITS_PATH,
    SOURCE_CHECK_PATH,
    rel_to_repo,
)
from src.utils.io import ensure_dir, write_json, write_yaml
from src.utils.logging import get_logger

LOGGER = get_logger("src.cli")

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_NOT_IMPLEMENTED = 2
EXIT_BLOCKED = 3

DEFAULT_CONFIG = CONFIGS_DIR / "base.yaml"
DEFAULT_SOURCES = CONFIGS_DIR / "sources.yaml"

# Etapy pipeline'u, ktore nalezą do pozniejszych faz. Mapowanie na zadania
# z docs/07_TASKS.md, zeby komunikat mowil, co dokladnie trzeba zrobic.
PENDING_STAGES: dict[str, str] = {
    "data": "T-012 (P1) — T-009/T-010/T-011: download-eqtb, formalize-qac-fallback, select-ctrl",
    # T-014 (ewaluacja na Koranie) jest zaimplementowane jako komenda `tag`.
    # T-015 (tagowanie CTRL) zostaje klastrowe: `tag-ctrl` / H1.
    # T-016: `clean-quotes`. T-017: `dedup`. T-018: `chronology`.
    # T-019: `segment`. T-020: `splits`. T-021/T-022: `features --family character|function`.
    "gates": "T-029..T-032 (P3)",
    "chrono": "T-043..T-047 (P6)",
    "explore": "T-048 (P6)",
    "figs": "T-035..T-047 (figury z results/)",
    "dashboard": "T-049 (P6)",
    "audit": "T-052 (P6)",
    "sample-run": "T-051 (P6)",
    # T-015 / H1: `tag --corpus ctrl` i `tag-ctrl` sa zaimplementowane, ale
    # Makefile blokuje je na laptopie. `build-handoff` / `verify-handoff` tez.
    "variance-array": "T-035 / H2 — zadanie klastrowe",
    "av-train": "T-038, T-039 / H2 — zadanie klastrowe",
    "embed": "T-048 / H3 — zadanie klastrowe",
}


class StageNotImplementedError(RuntimeError):
    """Etap nalezy do pozniejszej fazy backlogu."""


def _load(args: argparse.Namespace) -> Config:
    overlays = [Path(p) for p in (args.overlay or [])]
    return load_config(Path(args.config), overlays=overlays)


# --------------------------------------------------------------------------
# Podkomendy P0
# --------------------------------------------------------------------------


def cmd_hash_config(args: argparse.Namespace) -> int:
    config = _load(args)
    print(config.config_hash())
    return EXIT_OK


def cmd_show_config(args: argparse.Namespace) -> int:
    import json

    config = _load(args)
    print(json.dumps(config.hashable_payload(), ensure_ascii=False, indent=2, sort_keys=True))
    return EXIT_OK


def cmd_init_env(args: argparse.Namespace) -> int:
    """Tworzy `configs/env.local.yaml` z HOST_ROLE=laptop (11_HANDOFF §6).

    Plik jest poza gitem. Agent nie ma jak przelaczyc sie na `cluster`, bo nie
    ma tam dostepu — na klastrze robisz to recznie.
    """
    path = Path(args.path) if args.path else ENV_LOCAL_PATH
    if path.exists() and not args.force:
        print(f"{path} juz istnieje — zostawiam bez zmian (uzyj --force, zeby nadpisac).")
        return EXIT_OK
    write_yaml(path, {"host_role": "laptop"})
    print(f"Zapisano {path} (host_role: laptop).")
    return EXIT_OK


def cmd_verify_sources(args: argparse.Namespace) -> int:
    from src.data.verify_sources import (
        RequestsFetcher,
        load_sources,
        verify_sources,
    )
    from src.utils.runs import log_blocker, log_run

    config = _load(args)
    sources = load_sources(Path(args.sources))
    report = verify_sources(sources, RequestsFetcher())

    out_path = Path(args.out) if args.out else SOURCE_CHECK_PATH
    write_json(out_path, report.model_dump(mode="json"))

    for check in report.sources:
        marker = {
            "ok": "OK      ",
            "degraded": "DEGRADED",
            "fallback_active": "FALLBACK",
            "fail": "FAIL    ",
        }[check.status]
        print(f"{marker} {check.id:<20} {check.title}")
        for note in check.notes:
            print(f"         - {note}")

    print(f"\nOverall: {report.overall.upper()}  ->  {out_path}")

    failed = report.failed_required()
    for check in failed:
        # AGENTS.md: niedostepne zrodlo albo niezgodny format to jeden z czterech
        # przypadkow "zatrzymaj sie i zapytaj". Zapisujemy pytanie, nie zgadujemy.
        log_blocker(
            task="verify-sources",
            question=(
                f"Zrodlo '{check.id}' ({check.title}) nie przeszlo weryfikacji. "
                f"Uwagi: {'; '.join(check.notes) or 'brak'}. "
                "Czy uzywamy innego adresu/wersji, czy wstrzymujemy P1?"
            ),
            context=(
                f"{check.decision_ref} | zaobserwowano: {check.resolved} | "
                f"brakujace kolumny: {check.columns_missing}"
            ),
            source=check.url or "",
            artifacts=[rel_to_repo(out_path)],
        )

    log_run(
        task="verify-sources",
        status="blocked" if failed else "done",
        config_hash=config.config_hash(),
        artifacts=[rel_to_repo(out_path)],
        metrics={
            "n_sources": len(report.sources),
            "n_ok": sum(1 for s in report.sources if s.status == "ok"),
            "n_degraded": sum(1 for s in report.sources if s.status == "degraded"),
            "n_fallback_active": sum(1 for s in report.sources if s.status == "fallback_active"),
            "n_fail": sum(1 for s in report.sources if s.status == "fail"),
        },
        note=f"overall={report.overall}",
    )
    return EXIT_BLOCKED if failed else EXIT_OK


def cmd_download_eqtb(args: argparse.Namespace) -> int:
    """T-009: pobranie + parsowanie EQTB (docs/09_DECISIONS.md §2.1).

    `corpus/Quranic.rar` -> `Quranic.csv`, mapowanie kolumn wg `configs/sources.yaml`
    (`constituents_loc` -> `constituent_position` potwierdzone; `constituent_node`
    nierozstrzygniete, zostaje nullable). Liczba sur jest WERYFIKOWANA, nie
    przepisana (AGENTS.md zasada 8) — 114 to oczekiwanie z 09_DECISIONS.md §2.4,
    nie zalozenie.
    """
    from src.data.download_eqtb import (
        EqtbDownloadError,
        MissingSevenZipError,
        download_and_parse_eqtb,
    )
    from src.paths import RESULTS_DIR, rel_to_repo
    from src.utils.io import read_json, write_json
    from src.utils.runs import log_blocker, log_run

    config = _load(args)
    corpus_stats_path = RESULTS_DIR / "corpus_stats.json"

    try:
        result = download_and_parse_eqtb(force=args.force)
    except MissingSevenZipError as exc:
        print(f"BLAD: {exc}", file=sys.stderr)
        return EXIT_FAIL
    except EqtbDownloadError as exc:
        log_blocker(
            task="T-009",
            question=f"Pobranie/parsowanie EQTB zawiodlo: {exc}",
            context="docs/09_DECISIONS.md §2.1",
            source="https://github.com/NoorBayan/Quranic",
        )
        log_run(task="T-009", status="blocked", config_hash=config.config_hash(), note=str(exc))
        return EXIT_BLOCKED

    stats = result.stats
    stat_keys = (
        "n_raw_rows",
        "n_root_placeholder_rows",
        "n_segments",
        "n_tokens",
        "n_surahs",
        "n_verses",
    )
    artifacts = [rel_to_repo(result.tokens_path)]
    print(f"zapisano {rel_to_repo(result.tokens_path)} (from_cache={result.from_cache})")
    for key in stat_keys:
        print(f"  {key}: {stats[key]}")

    corpus_stats = read_json(corpus_stats_path) if corpus_stats_path.exists() else {}
    corpus_stats["eqtb"] = {
        **{k: stats[k] for k in stat_keys},
        "source": "corpus/Quranic.rar -> Quranic.csv",
        "annotation_source": "silver (warstwa skladniowa BiLSTM, 09_DECISIONS.md §2.1)",
        "token_unit": "orthographic_word (docs/09_DECISIONS.md §6); n_segments = wiersze/morfemy",
    }
    write_json(corpus_stats_path, corpus_stats)
    artifacts.append(rel_to_repo(corpus_stats_path))

    if stats["n_surahs"] != 114:
        # 09_DECISIONS.md §2.4: 114 sur jest weryfikowane, nie przepisane.
        # Rozbieznosc = jeden z czterech przypadkow "zatrzymaj sie i zapytaj".
        log_blocker(
            task="T-009",
            question=(
                f"Policzono {stats['n_surahs']} sur w EQTB, oczekiwano 114 "
                "(09_DECISIONS.md §2.4). Zle zmapowana kolumna chapter_id, czy "
                "naprawde niekompletne dane?"
            ),
            context="results/corpus_stats.json:eqtb",
            artifacts=artifacts,
        )
        log_run(
            task="T-009",
            status="blocked",
            config_hash=config.config_hash(),
            artifacts=artifacts,
            metrics=stats,
        )
        return EXIT_BLOCKED

    log_run(
        task="T-009",
        status="done",
        config_hash=config.config_hash(),
        artifacts=artifacts,
        metrics={k: stats[k] for k in stat_keys},
        note=f"from_cache={result.from_cache}",
    )
    return EXIT_OK


def cmd_formalize_qac_fallback(args: argparse.Namespace) -> int:
    """T-010: formalizacja fallbacku QAC, bez pobierania (09_DECISIONS.md §2.2)."""
    from src.data.download_qac import QacDownloadForbiddenError, formalize_qac_fallback
    from src.utils.runs import log_run

    config = _load(args)
    try:
        result = formalize_qac_fallback()
    except QacDownloadForbiddenError as exc:
        print(f"BLAD: {exc}", file=sys.stderr)
        return EXIT_FAIL

    artifact = rel_to_repo(result.artifact_path)
    print(f"zapisano {artifact}")
    print(f"  status: {result.payload['status']}")
    print(f"  reference_corpus: {result.payload['reference_corpus']}")
    print(f"  qac_downloaded: {result.payload['qac_downloaded']}")

    log_run(
        task="T-010",
        status="done",
        config_hash=config.config_hash(),
        artifacts=[
            artifact,
            "results/source_check.json",
            "results/eqtb_vs_qac_per_surah.csv",
            "SOURCES.md",
        ],
        metrics={
            "qac_downloaded": 0,
            "qac_status_is_fallback_active": 1,
            "qac_java_api_n_tokens": result.payload["qac_java_api_n_tokens"],
        },
        note=(
            "Nie pobrano QAC. Fallback z 09_DECISIONS.md par.2.2 sformalizowany: "
            "referencja T-014 = kolumny morfologiczne EQTB. "
            "qac.status=fallback_active, nie degraded."
        ),
    )
    return EXIT_OK


def cmd_select_ctrl(args: argparse.Namespace) -> int:
    """T-011: pelny algorytm §3 (genre przed jakoscia, filtr gatunkowo-zalezny)."""
    from src.data.select_ctrl import HARD_MINIMA, run_select_ctrl
    from src.paths import CTRL_MANIFEST_PATH
    from src.utils.runs import log_blocker, log_run, resolve_blockers

    config = _load(args)
    resolve_blockers(
        "T-011",
        "Rozstrzygniete w docs/09_DECISIONS.md §3–§4: tagi OpenITI jako sygnal "
        "glowny; genre przed jakoscia; mean_word_length 2.5 dla "
        "poetry_diwan/maqamat_saj; long_line_ratio usuniete; language=ara. "
        "Krok 5: standard LUB single_work_exception (n_books==1 AND "
        "book_tokens>=15000) dla czterech gatunkow z twardym minimum — "
        "minimum maqamat_saj zostaje 3.",
    )

    summary = run_select_ctrl(
        workers=args.workers,
        download_texts=not args.skip_download,
    )

    print(f"autorzy: {summary['n_authors']}")
    print(f"gatunki (primary): {summary['genre_counts']}")
    print(f"pokrycie twardych minimow: {summary['coverage_counts']}")
    print(
        f"single_work_exception: {summary['n_single_work_exception']} {summary['exception_counts']}"
    )
    print(f"other_share: {summary['other_share']:.3f}")
    print(f"prog_tokenow: {summary['token_threshold_used']}")
    print(f"luzowanie_20000: {summary['relaxed_to_20000']}")
    for note in summary["notes"]:
        print(f"  - {note}")

    artifacts = ["results/ctrl_selection.json", "data/reference/openiti_tag_genre_map.csv"]
    if summary.get("manifest"):
        artifacts.append(rel_to_repo(CTRL_MANIFEST_PATH))

    metrics = {
        "n_authors": summary["n_authors"],
        "n_books_selected": summary["n_books_selected"],
        "other_share": summary["other_share"],
        "relaxed_to_20000": int(summary["relaxed_to_20000"]),
        "minima_ok": int(summary["minima_ok"]),
        "n_single_work_exception": summary["n_single_work_exception"],
        **{f"n_{g}": summary["coverage_counts"].get(g, 0) for g in HARD_MINIMA},
    }

    if summary["blocked"]:
        log_blocker(
            task="T-011",
            question=(
                f"Po pelnym algorytmie §3: autorow={summary['n_authors']} "
                f"(min 60), minima={summary['genre_counts']} vs {HARD_MINIMA}. "
                f"Uwagi: {'; '.join(summary['notes'])}. Jak luzujemy kryteria?"
            ),
            context="docs/09_DECISIONS.md §3–§4 | results/ctrl_selection.json",
            source="OpenITI metadata 2025.1.9",
            artifacts=artifacts,
        )
        log_run(
            task="T-011",
            status="blocked",
            config_hash=config.config_hash(),
            artifacts=artifacts,
            metrics=metrics,
            note="; ".join(summary["notes"]),
        )
        return EXIT_BLOCKED

    log_run(
        task="T-011",
        status="done",
        config_hash=config.config_hash(),
        artifacts=artifacts,
        metrics=metrics,
        note="; ".join(summary["notes"]),
    )
    return EXIT_OK


def cmd_normalize(args: argparse.Namespace) -> int:
    """T-013: normalizator (03_DATA §4). Wejscie CTRL z dysku; Koran = imlaai_token."""
    from src.data.normalize_arabic import benchmark_ctrl
    from src.data.select_ctrl import SELECTED_TEXT_DIR
    from src.utils.io import write_json
    from src.utils.runs import log_run

    config = _load(args)
    files = (
        sorted(p for p in SELECTED_TEXT_DIR.iterdir() if p.is_file())
        if SELECTED_TEXT_DIR.is_dir()
        else []
    )
    if not files:
        print(
            "BRAK plikow CTRL w data/raw/openiti/selected — T-011 musi byc na dysku.",
            file=sys.stderr,
        )
        return EXIT_FAIL

    bench = benchmark_ctrl(files)
    payload = {
        "markdown_step0_required": True,
        "markdown_probe": "results/t013_markdown_probe.json",
        "quran_input": "imlaai_token (EQTB) — ten sam normalize(); nie uruchamiane tu przed FREEZE",
        **bench,
    }
    out = RESULTS_DIR / "normalize_benchmark.json"
    write_json(out, payload)
    print(
        f"strict {bench['elapsed_sec_strict']}s "
        f"tokens {bench['n_tokens_before']}->{bench['n_tokens_after_strict']}"
    )
    print(
        f"light  {bench['elapsed_sec_light']}s "
        f"tokens {bench['n_tokens_before']}->{bench['n_tokens_after_light']}"
    )
    print(
        f"step0_markdown=required total={bench['elapsed_sec_total']}s "
        f"empty_sample={bench['token_list_sample_empty']}/{bench['token_list_sample_n']}"
    )

    log_run(
        task="T-013",
        status="done",
        config_hash=config.config_hash(),
        artifacts=[
            rel_to_repo(out),
            "results/t013_markdown_probe.json",
            "src/data/normalize_arabic.py",
        ],
        metrics={
            "elapsed_sec_strict": bench["elapsed_sec_strict"],
            "elapsed_sec_light": bench["elapsed_sec_light"],
            "elapsed_sec_total": bench["elapsed_sec_total"],
            "n_tokens_before": bench["n_tokens_before"],
            "n_tokens_after": bench["n_tokens_after_strict"],
            "n_empty_after_sample": bench["token_list_sample_empty"],
            "n_files": bench["n_files"],
            "markdown_step0_required": 1,
            "under_5_min": int(bench["under_5_min"]),
        },
        note=(
            "Krok 0 mARkdown wymagany (10/10 plikow T-011 na dysku ma markup; "
            "T-011 czyscilo tylko w pamieci przy quality). "
            "light = bez pkt 5–6. Wejscie Koranu: imlaai_token."
        ),
    )
    return EXIT_OK


def cmd_cap_ctrl(args: argparse.Namespace) -> int:
    """Limit 200k tokenow per autor (09_DECISIONS.md §3). Nie taguje, nie buduje H1."""
    from src.data.cap_ctrl import CAP_SUMMARY_PATH, CAPPED_MANIFEST_PATH, run_ctrl_cap
    from src.utils.runs import log_run

    config = _load(args)
    limit = int(config.corpus.max_tokens_per_author or 200_000)
    try:
        summary = run_ctrl_cap(
            limit=limit,
            config_seed=config.seed,
            profile=config.normalizer.profile,
        )
    except FileNotFoundError as exc:
        print(f"BLAD: {exc}", file=sys.stderr)
        return EXIT_FAIL

    print(
        f"cap-ctrl limit={limit} tokens_after={summary['tokens_after']} "
        f"clipped={summary['n_authors_clipped']}/{summary['n_authors']} "
        f"books_zeroed={summary['n_books_zeroed']}"
    )
    print(f"  sanity_no_book_zeroed={summary['sanity_no_book_zeroed']}")
    print(
        f"  sanity_author_total_ge_max_book_after="
        f"{summary['sanity_author_total_ge_max_book_after']}"
    )

    log_run(
        task="T-013b",
        status="done",
        config_hash=config.config_hash(),
        artifacts=[
            rel_to_repo(CAP_SUMMARY_PATH),
            rel_to_repo(CAPPED_MANIFEST_PATH),
            "data/interim/ctrl_capped/",
        ],
        metrics={
            "limit": summary["limit"],
            "n_authors": summary["n_authors"],
            "n_authors_clipped": summary["n_authors_clipped"],
            "tokens_before": summary["tokens_before"],
            "tokens_after": summary["tokens_after"],
            "n_books_zeroed": summary["n_books_zeroed"],
            "sanity_no_book_zeroed": int(summary["sanity_no_book_zeroed"]),
        },
        note=(
            "Limit 200k/autor, alokacja proporcjonalna, losowy ciagly fragment "
            "(09_DECISIONS.md par.3). Normalize(strict) z T-013, bez ponownego benchmarku."
        ),
    )
    return EXIT_OK


def cmd_tag(args: argparse.Namespace) -> int:
    corpus = getattr(args, "corpus", None) or "quran"
    if corpus == "ctrl":
        return cmd_tag_ctrl(args)
    return cmd_tag_quran(args)


def cmd_tag_quran(args: argparse.Namespace) -> int:
    """T-014: ewaluacja CAMeL vs EQTB gold na Koranie."""
    from src.annotate.evaluate_tagger import TAGGER_EVAL_PATH, run_quran_eval
    from src.annotate.tagger import TaggerNotAvailableError
    from src.data.download_eqtb import INTERIM_TOKENS_PATH
    from src.utils.runs import log_run

    config = _load(args)
    eqtb_path = Path(args.eqtb) if getattr(args, "eqtb", None) else INTERIM_TOKENS_PATH
    out_path = Path(args.out) if getattr(args, "out", None) else TAGGER_EVAL_PATH
    max_words = int(args.max_words) if getattr(args, "max_words", None) else None
    skip_fig = bool(getattr(args, "skip_fig", False))
    try:
        payload = run_quran_eval(
            eqtb_path=eqtb_path,
            out_path=out_path,
            max_words=max_words,
            config_hash=config.config_hash(),
            tagger_version=config.tagger.version,
            database=config.tagger.database,
            disambiguator=config.tagger.disambiguator,
            write_figure=not skip_fig,
        )
    except FileNotFoundError as exc:
        print(f"BLAD: {exc}", file=sys.stderr)
        return EXIT_FAIL
    except TaggerNotAvailableError as exc:
        print(f"BLAD: {exc}", file=sys.stderr)
        return EXIT_FAIL

    metrics = payload["metrics"]
    print(f"zapisano {rel_to_repo(out_path)}")
    print(
        f"  n_words={payload['n_words']}  pos_coarse={metrics['pos_accuracy_coarse']:.4f}  "
        f"pos_fine={metrics['pos_accuracy']:.4f}  lemma={metrics['lemma_accuracy']:.4f}  "
        f"seg_f1={metrics['segmentation_f1']:.4f}"
    )

    artifacts = [rel_to_repo(out_path), "data/reference/eqtb_camel_pos_map.csv"]
    if payload.get("figure"):
        artifacts.extend(
            [
                payload["figure"]["png"],
                payload["figure"]["svg"],
                payload["figure"]["json"],
            ]
        )

    log_run(
        task="T-014",
        status="done",
        config_hash=config.config_hash(),
        artifacts=artifacts,
        metrics={
            "n_words": payload["n_words"],
            "pos_accuracy": metrics["pos_accuracy"],
            "pos_accuracy_coarse": metrics["pos_accuracy_coarse"],
            "lemma_accuracy": metrics["lemma_accuracy"],
            "segmentation_f1": metrics["segmentation_f1"],
            "alignment_coverage": metrics["alignment_coverage"],
            "majority_baseline_coarse": metrics["majority_baseline_coarse"],
            "ctrl_tagged": 0,
        },
        note="T-014 Koran-only: CAMeL MLE vs EQTB gold (T-010 fallback, nie QAC).",
    )
    return EXIT_OK


def cmd_tag_ctrl(args: argparse.Namespace) -> int:
    """T-015: tagowanie CTRL. Na laptopie blokowane (11_HANDOFF)."""
    from src.annotate.tag_ctrl import PILOT_PATH, make_tagger, tag_ctrl_corpus
    from src.annotate.tagger import TaggerNotAvailableError
    from src.config import load_env_local
    from src.paths import CTRL_CAPPED_DIR, DATA_INTERIM_DIR
    from src.utils.runs import log_run

    env = load_env_local()
    if env.host_role != "cluster":
        print(
            "BLOCKED: tagowanie CTRL (T-015, BERT) jest zadaniem klastrowym. "
            "Przygotuj paczke: make handoff JOB=H1. Nie uruchamiam sbatch.",
            file=sys.stderr,
        )
        return EXIT_FAIL

    config = _load(args)
    input_dir = Path(args.input) if getattr(args, "input", None) else CTRL_CAPPED_DIR
    output_dir = (
        Path(args.output) if getattr(args, "output", None) else DATA_INTERIM_DIR / "ctrl_tagged"
    )
    disambiguator = getattr(args, "disambiguator", None) or "bert"
    batch_size = int(getattr(args, "batch_size", None) or 64)
    checkpoint_every = int(getattr(args, "checkpoint_every", None) or 200)
    limit_tokens = getattr(args, "limit_tokens", None)
    pilot = bool(getattr(args, "pilot", False))
    try:
        tagger = make_tagger(disambiguator, config.tagger.database)
        payload = tag_ctrl_corpus(
            tagger=tagger,
            input_dir=input_dir,
            output_dir=output_dir,
            batch_size=batch_size,
            checkpoint_every=checkpoint_every,
            limit_tokens=int(limit_tokens) if limit_tokens else None,
            disambiguator=disambiguator,
            config_hash=config.config_hash(),
            pilot=pilot,
        )
    except (FileNotFoundError, TaggerNotAvailableError, ValueError) as exc:
        print(f"BLAD: {exc}", file=sys.stderr)
        return EXIT_FAIL

    print(
        f"tag-ctrl files={payload['n_files']} tokens={payload['n_tokens']} "
        f"tok/s={payload['tokens_per_sec']:.2f}"
    )
    if payload.get("pilot"):
        print(f"  recommended --time {payload['pilot']['slurm_time']}")
        print(f"  zapisano {rel_to_repo(PILOT_PATH)}")

    log_run(
        task="T-015",
        status="done" if not pilot else "done",
        config_hash=config.config_hash(),
        artifacts=[rel_to_repo(output_dir)] + ([rel_to_repo(PILOT_PATH)] if pilot else []),
        metrics={
            "n_tokens": payload["n_tokens"],
            "tokens_per_sec": payload["tokens_per_sec"],
            "pilot": int(pilot),
        },
        note="T-015 CTRL BERT" + (" (pilot dryrun)" if pilot else ""),
        host="cluster",
    )
    return EXIT_OK


def cmd_clean_quotes(args: argparse.Namespace) -> int:
    """T-016: cytaty Koranu w CTRL. T-017 (redundancja wewnetrzna) osobno."""
    import pandas as pd

    from src.data.detect_quran_quotes import (
        EQTB_TOKENS_PATH,
        OPENITI_CLEAN_DIR,
        QUOTE_AUDIT_PATH,
        QUOTE_REPORT_PATH,
        clean_ctrl_quotes,
        make_fuzzy_index,
        quran_word_tokens,
        write_quote_artifacts,
    )
    from src.paths import CTRL_CAPPED_DIR, rel_to_repo
    from src.utils.runs import log_run
    from src.viz.fig05_quotes import save_fig_05

    config = _load(args)
    eqtb_path = Path(args.eqtb) if getattr(args, "eqtb", None) else EQTB_TOKENS_PATH
    if not eqtb_path.exists():
        print(f"BLAD: brak {eqtb_path} (T-009).", file=sys.stderr)
        return EXIT_FAIL
    input_dir = Path(args.input) if getattr(args, "input", None) else CTRL_CAPPED_DIR
    output_dir = Path(args.output) if getattr(args, "output", None) else OPENITI_CLEAN_DIR
    if not input_dir.is_dir():
        print(f"BLAD: brak {input_dir} (T-013b).", file=sys.stderr)
        return EXIT_FAIL

    eqtb = pd.read_parquet(eqtb_path)
    quran_tokens = quran_word_tokens(eqtb, profile=config.normalizer.profile)
    skip_fuzzy = bool(getattr(args, "skip_fuzzy", False))
    fuzzy = None if skip_fuzzy else make_fuzzy_index(config.quotes)
    limit = getattr(args, "limit_books", None)
    payload = clean_ctrl_quotes(
        quran_tokens=quran_tokens,
        input_dir=input_dir,
        output_dir=output_dir,
        cfg=config.quotes,
        seed=config.seed,
        fuzzy=fuzzy,
        limit_books=int(limit) if limit else None,
    )
    paths = write_quote_artifacts(payload, config_hash=config.config_hash())
    report = payload["report"]
    totals = report["totals"]
    print(
        f"clean-quotes books={totals['n_books']} "
        f"raw={totals['tokens_raw']} removed={totals['tokens_removed']} "
        f"shuffle={totals['tokens_shuffle_removed']}"
    )
    print(f"  zapisano {rel_to_repo(paths['report'])}")
    print(f"  audyt (reczny, 2x100): {rel_to_repo(paths['audit'])}")
    audit = report.get("audit") or {}
    if audit.get("precision") is not None:
        print(
            f"  precision={audit['precision']} "
            f"recall_sample={audit.get('recall_sample')} "
            f"pending_human={audit.get('pending_human')}"
        )
    if not getattr(args, "skip_fig", False):
        saved = save_fig_05(report, config_hash=config.config_hash())
        print(f"  figura {rel_to_repo(saved.png)}")

    log_run(
        task="T-016",
        status="done",
        config_hash=config.config_hash(),
        artifacts=[
            rel_to_repo(output_dir),
            rel_to_repo(QUOTE_REPORT_PATH),
            rel_to_repo(QUOTE_AUDIT_PATH),
            "figures/FIG-05_quote_removal.png",
        ],
        metrics={
            "n_books": totals["n_books"],
            "tokens_raw": totals["tokens_raw"],
            "tokens_removed": totals["tokens_removed"],
            "tokens_shuffle_removed": totals["tokens_shuffle_removed"],
            "audit_pending": int(bool((report.get("audit") or {}).get("pending_human"))),
            "precision": (report.get("audit") or {}).get("precision"),
            "recall_sample": (report.get("audit") or {}).get("recall_sample"),
        },
        note=(
            "T-016: exact 7-gram + concat-fold (اا→ا, ءا→ا) + MinHash/LSH + margines ±3. "
            "Audyt 2×100 w quote_audit_sample.json."
        ),
    )
    return EXIT_OK


def cmd_dedup(args: argparse.Namespace) -> int:
    """T-017: redundancja wewnetrzna (nie cytaty T-016)."""
    from src.data.dedup import run_internal_duplication, write_duplication_report
    from src.paths import OPENITI_CLEAN_DIR, OPENITI_DEDUP_DIR
    from src.utils.runs import log_run
    from src.viz.fig06_duplication import save_fig_06

    config = _load(args)
    ctrl_dir = Path(args.input) if getattr(args, "input", None) else OPENITI_CLEAN_DIR
    if not ctrl_dir.is_dir():
        print(f"BLAD: brak {ctrl_dir} (T-016).", file=sys.stderr)
        return EXIT_FAIL
    try:
        payload = run_internal_duplication(
            n=config.quotes.quote_ngram_n,
            seed=config.seed,
            ctrl_dir=ctrl_dir,
            limit_books=int(args.limit_books) if getattr(args, "limit_books", None) else None,
            write_dedup=not bool(getattr(args, "skip_write_dedup", False)),
            profile=config.normalizer.profile,
        )
    except FileNotFoundError as exc:
        print(f"BLAD: {exc}", file=sys.stderr)
        return EXIT_FAIL
    write_duplication_report(payload, config_hash=config.config_hash())
    q_rate = payload["quran"]["raw"]["internal_duplication_rate"]
    c_rate = payload["ctrl"]["raw"]["internal_duplication_rate"]
    print(
        f"dedup quran_rate={q_rate:.4f} ctrl_rate={c_rate:.4f} "
        f"ctrl_books={payload['n_ctrl_books']}"
    )
    print(f"  zapisano {rel_to_repo(INTERNAL_DUP_PATH)}")
    if payload.get("dedup_dir"):
        print(f"  dedup CTRL: {payload['dedup_dir']}")
    if not getattr(args, "skip_fig", False):
        saved = save_fig_06(payload, config_hash=config.config_hash())
        print(f"  figura {rel_to_repo(saved.png)}")
    log_run(
        task="T-017",
        status="done",
        config_hash=config.config_hash(),
        artifacts=[
            rel_to_repo(INTERNAL_DUP_PATH),
            rel_to_repo(OPENITI_DEDUP_DIR),
            "figures/FIG-06_internal_duplication.png",
        ],
        metrics={
            "quran_duplication_rate": q_rate,
            "ctrl_duplication_rate": c_rate,
            "quran_shuffle_rate": payload["quran"]["shuffle"]["internal_duplication_rate"],
            "ctrl_shuffle_rate": payload["ctrl"]["shuffle"]["internal_duplication_rate"],
            "n_ctrl_books": payload["n_ctrl_books"],
        },
        note="T-017: internal_duplication_rate typy 7-gramow; wariant dedup + shuffle G9.",
    )
    return EXIT_OK


def cmd_segment(args: argparse.Namespace) -> int:
    """T-019: okna. T-020 (splity autorow) osobno."""
    from src.data.segment import run_segmentation, write_segmentation_report
    from src.paths import OPENITI_CLEAN_DIR
    from src.utils.runs import log_run

    config = _load(args)
    ctrl_dir = Path(args.input) if getattr(args, "input", None) else OPENITI_CLEAN_DIR
    sizes = None
    if getattr(args, "sizes", None):
        sizes = [int(x) for x in str(args.sizes).split(",") if x.strip()]
    try:
        payload = run_segmentation(
            cfg=config.segmentation,
            normalizer_version=f"{config.normalizer.profile}-{config.normalizer.version}",
            tagger_version=config.tagger.version,
            profile=config.normalizer.profile,
            ctrl_dir=ctrl_dir,
            limit_books=int(args.limit_books) if getattr(args, "limit_books", None) else None,
            sizes=sizes,
            write_olap=not bool(getattr(args, "skip_olap", False)),
        )
    except FileNotFoundError as exc:
        print(f"BLAD: {exc}", file=sys.stderr)
        return EXIT_FAIL
    write_segmentation_report(payload, config_hash=config.config_hash())
    main = (payload.get("sizes") or {}).get(str(config.segmentation.window_size), {})
    qn = (main.get("quran") or {}).get("n_windows")
    cn = (main.get("ctrl") or {}).get("n_windows")
    print(f"segment window_size={config.segmentation.window_size} quran_n={qn} ctrl_n={cn}")
    print(f"  zapisano {rel_to_repo(SEGMENTATION_REPORT_PATH)}")
    log_run(
        task="T-019",
        status="done",
        config_hash=config.config_hash(),
        artifacts=[rel_to_repo(SEGMENTATION_REPORT_PATH), "data/processed/windows_400/"],
        metrics={
            "n_windows_quran": qn or 0,
            "n_windows_ctrl": cn or 0,
            "n_composite_quran": (main.get("quran") or {}).get("n_composite") or 0,
            "tokens_in_composite": (main.get("quran") or {}).get("tokens_in_composite") or 0,
        },
        note="T-019: okna G3. split CTRL=ctrl_test do T-020. T-020 nie wchodzi w ten przebieg.",
    )
    return EXIT_OK


def cmd_splits(args: argparse.Namespace) -> int:
    """T-020: splity autorow. Nie T-021."""
    from src.data.splits import run_splits, write_splits_report
    from src.utils.runs import log_run

    config = _load(args)
    try:
        payload = run_splits(
            ratios=config.splits.model_dump(),
            seed=config.seed,
            apply_windows=not bool(getattr(args, "skip_windows", False)),
        )
    except FileNotFoundError as exc:
        print(f"BLAD: {exc}", file=sys.stderr)
        return EXIT_FAIL
    write_splits_report(payload, config_hash=config.config_hash())
    by_split = payload.get("n_by_split") or {}
    print(
        f"splits n_authors={payload['n_authors']} "
        f"train={by_split.get('ctrl_train')} "
        f"calib={by_split.get('ctrl_calib')} "
        f"test={by_split.get('ctrl_test')} "
        f"windows={len(payload.get('windows_updated') or [])}"
    )
    print(f"  zapisano {rel_to_repo(SPLITS_PATH)}")
    log_run(
        task="T-020",
        status="done",
        config_hash=config.config_hash(),
        artifacts=[rel_to_repo(SPLITS_PATH), "data/processed/windows_400/ctrl.parquet"],
        metrics={
            "n_authors": payload["n_authors"],
            "n_train": by_split.get("ctrl_train") or 0,
            "n_calib": by_split.get("ctrl_calib") or 0,
            "n_test": by_split.get("ctrl_test") or 0,
            "n_window_files": len(payload.get("windows_updated") or []),
        },
        note="T-020: split po author_id, stratyfikacja genre x epoka. Quran=target.",
    )
    return EXIT_OK


def cmd_features(args: argparse.Namespace) -> int:
    """T-021..T-028 dispatcher. T-021 = character, T-022 = function_words."""
    family = str(getattr(args, "family", "character") or "character")
    if family in {"function", "function_words", "functional"}:
        return _cmd_features_function(args)
    if family in {"lexical", "lex", "word"}:
        return _cmd_features_lexical(args)
    if family != "character":
        print(
            f"NIEZAIMPLEMENTOWANE: rodzina '{family}' nalezy do T-024..T-028.",
            file=sys.stderr,
        )
        return EXIT_NOT_IMPLEMENTED
    from src.features.character import run_character_features, write_character_report
    from src.utils.runs import log_run

    config = _load(args)
    try:
        payload = run_character_features(
            config,
            skip_fig=bool(getattr(args, "skip_fig", False)),
            limit=int(args.limit) if getattr(args, "limit", None) else None,
        )
    except FileNotFoundError as exc:
        print(f"BLAD: {exc}", file=sys.stderr)
        return EXIT_FAIL
    write_character_report(payload, config_hash=config.config_hash())
    main = (payload.get("variants") or {}).get("main") or {}
    print(
        f"features character n_windows={payload.get('n_windows')} "
        f"n_train={payload.get('n_ctrl_train')} "
        f"n_cols={main.get('n_cols')} "
        f"norm_r={((main.get('norm_token') or {}).get('r'))}"
    )
    print(f"  zapisano {rel_to_repo(CHARACTER_REPORT_PATH)}")
    if payload.get("figure"):
        print(f"  figura {payload['figure']}")
    log_run(
        task="T-021",
        status="done",
        config_hash=config.config_hash(),
        artifacts=[
            rel_to_repo(CHARACTER_REPORT_PATH),
            str(main.get("dir") or "data/features/character/"),
            str(payload.get("figure") or ""),
        ],
        metrics={
            "n_windows": payload.get("n_windows") or 0,
            "n_ctrl_train": payload.get("n_ctrl_train") or 0,
            "n_cols": main.get("n_cols") or 0,
            "norm_token_r": (main.get("norm_token") or {}).get("r") or 0.0,
            "n_zero_rows": main.get("n_zero_rows") or 0,
        },
        note="T-021: F1 char_wb 3-5, fit CTRL-TRAIN. Wariant no_diacritics_no_ligatures. E-01=T-029.",
    )
    return EXIT_OK


def _cmd_features_function(args: argparse.Namespace) -> int:
    from src.annotate.tagger import TaggerNotAvailableError
    from src.features.function_words import run_function_word_features, write_function_report
    from src.schemas import GuardrailViolationError
    from src.utils.runs import log_run

    config = _load(args)
    try:
        payload = run_function_word_features(
            config,
            skip_fig=bool(getattr(args, "skip_fig", False)),
            limit=int(args.limit) if getattr(args, "limit", None) else None,
        )
    except FileNotFoundError as exc:
        print(f"BLAD: {exc}", file=sys.stderr)
        return EXIT_FAIL
    except (GuardrailViolationError, TaggerNotAvailableError) as exc:
        print(f"BLAD: {exc}", file=sys.stderr)
        return EXIT_FAIL
    write_function_report(payload, config_hash=config.config_hash())
    main = (payload.get("variants") or {}).get("k1000") or next(
        iter((payload.get("variants") or {}).values()), {}
    )
    print(
        f"features function_words n_windows={payload.get('n_windows')} "
        f"n_train={payload.get('n_ctrl_train')} "
        f"n_cols={main.get('n_cols')} "
        f"norm_r={((main.get('norm_token') or {}).get('r'))}"
    )
    print(f"  zapisano {rel_to_repo(FUNCTION_REPORT_PATH)}")
    if payload.get("figure"):
        print(f"  figura {payload['figure']}")
    log_run(
        task="T-022",
        status="done",
        config_hash=config.config_hash(),
        artifacts=[
            rel_to_repo(FUNCTION_REPORT_PATH),
            str(main.get("dir") or "data/features/function_words/"),
            str(payload.get("figure") or ""),
        ],
        metrics={
            "n_windows": payload.get("n_windows") or 0,
            "n_ctrl_train": payload.get("n_ctrl_train") or 0,
            "n_cols": main.get("n_cols") or 0,
            "norm_token_r": (main.get("norm_token") or {}).get("r") or 0.0,
            "n_zero_rows": main.get("n_zero_rows") or 0,
            "n_multi_segment_ctrl": payload.get("n_multi_segment_ctrl") or 0,
        },
        note="T-022: F2 function words, vocab CTRL-TRAIN, K=100/300/1000. E-01=T-029.",
    )
    return EXIT_OK


def _cmd_features_lexical(args: argparse.Namespace) -> int:
    from src.annotate.tagger import TaggerNotAvailableError
    from src.features.lexical import run_lexical_features, write_lexical_report
    from src.schemas import GuardrailViolationError
    from src.utils.runs import log_blocker, log_run

    config = _load(args)
    try:
        payload = run_lexical_features(
            config,
            skip_fig=bool(getattr(args, "skip_fig", False)),
            limit=int(args.limit) if getattr(args, "limit", None) else None,
        )
    except FileNotFoundError as exc:
        print(f"BLAD: {exc}", file=sys.stderr)
        return EXIT_FAIL
    except (GuardrailViolationError, TaggerNotAvailableError) as exc:
        print(f"BLAD: {exc}", file=sys.stderr)
        return EXIT_FAIL
    write_lexical_report(payload, config_hash=config.config_hash())
    main = (payload.get("variants") or {}).get("word") or next(
        iter((payload.get("variants") or {}).values()), {}
    )
    print(
        f"features lexical n_windows={payload.get('n_windows')} "
        f"n_train={payload.get('n_ctrl_train')} "
        f"n_cols={main.get('n_cols')} "
        f"units={sorted((payload.get('variants') or {}).keys())} "
        f"norm_r={((main.get('norm_token') or {}).get('r'))}"
    )
    print(f"  zapisano {rel_to_repo(LEXICAL_REPORT_PATH)}")
    if payload.get("figure"):
        print(f"  figura {payload['figure']}")
    if payload.get("root_skipped"):
        log_blocker(
            task="T-023",
            question=(
                "Wariant F3 root pominiety: ctrl_tagged nie ma root_pred, a lookup "
                "CALIMA nie zwrocil rdzeni. Czy odtwarzamy root_pred na klastrze "
                "(dopisac kolumne do T-015), czy zostawiamy word+lemma?"
            ),
            context="configs/features/lexical.yaml units includes root; T-015 schema nie zapisuje root.",
            source="data/interim/ctrl_tagged/",
            artifacts=[rel_to_repo(LEXICAL_REPORT_PATH)],
        )
    log_run(
        task="T-023",
        status="done",
        config_hash=config.config_hash(),
        artifacts=[
            rel_to_repo(LEXICAL_REPORT_PATH),
            str(main.get("dir") or "data/features/lexical/"),
            str(payload.get("figure") or ""),
        ],
        metrics={
            "n_windows": payload.get("n_windows") or 0,
            "n_ctrl_train": payload.get("n_ctrl_train") or 0,
            "n_cols": main.get("n_cols") or 0,
            "norm_token_r": (main.get("norm_token") or {}).get("r") or 0.0,
            "n_zero_rows": main.get("n_zero_rows") or 0,
            "root_skipped": int(bool(payload.get("root_skipped"))),
            "n_lemma_cols": ((payload.get("variants") or {}).get("lemma") or {}).get("n_cols") or 0,
            "n_root_cols": ((payload.get("variants") or {}).get("root") or {}).get("n_cols") or 0,
        },
        note="T-023: F3 lexical word/lemma/root TF-IDF 1-2, fit CTRL-TRAIN, status=support. E-01=T-029.",
    )
    return EXIT_OK


def cmd_chronology(args: argparse.Namespace) -> int:
    """T-018: tabela chronologii + FIG-06b. Nie T-043 (chrono)."""
    from src.data.chronology import run_chronology_agreement, write_chronology_report
    from src.utils.runs import log_run
    from src.viz.fig06b_chronology import save_fig_06b

    config = _load(args)
    try:
        payload = run_chronology_agreement(seed=config.seed)
    except FileNotFoundError as exc:
        print(f"BLAD: {exc}", file=sys.stderr)
        return EXIT_FAIL
    write_chronology_report(payload, config_hash=config.config_hash())
    rho_tn = float(payload["rho_traditional_noldeke"])
    rho_ct = float(payload["rho_canonical_traditional"])
    shuf = float((payload.get("shuffle") or {}).get("rho_mean") or 0.0)
    print(
        f"chronology n={payload['n_surahs']} "
        f"rho_trad_noldeke={rho_tn:.4f} rho_canon_trad={rho_ct:.4f} "
        f"n_disagree={payload['n_rank_disagree_traditional_noldeke']} "
        f"shuffle_mean={shuf:.4f}"
    )
    print(f"  zapisano {rel_to_repo(CHRONOLOGY_AGREEMENT_PATH)}")
    if not getattr(args, "skip_fig", False):
        saved = save_fig_06b(payload, config_hash=config.config_hash())
        print(f"  figura {rel_to_repo(saved.png)}")
    log_run(
        task="T-018",
        status="done",
        config_hash=config.config_hash(),
        artifacts=[
            rel_to_repo(CHRONOLOGY_AGREEMENT_PATH),
            "data/reference/chronologies.csv",
            "figures/FIG-06b_chronology_agreement.png",
            "SOURCES.md",
        ],
        metrics={
            "n_surahs": payload["n_surahs"],
            "rho_traditional_noldeke": rho_tn,
            "rho_canonical_traditional": rho_ct,
            "n_rank_disagree_traditional_noldeke": payload[
                "n_rank_disagree_traditional_noldeke"
            ],
            "shuffle_rho_mean": shuf,
        },
        note=(
            "T-018: FIG-06b Spearman na 3 kolumnach CSV. Sadeghi nieobecny. "
            "rho policzone, nie przepisane. GdQ 1860 strony w SOURCES.md."
        ),
    )
    return EXIT_OK


def cmd_diagnose_adv(args: argparse.Namespace) -> int:
    from src.annotate.diagnose_adv import ADV_DIAGNOSIS_PATH, diagnose_adv
    from src.annotate.tagger import TaggerNotAvailableError
    from src.utils.runs import log_run

    config = _load(args)
    try:
        payload = diagnose_adv(seed=config.seed)
    except (FileNotFoundError, TaggerNotAvailableError) as exc:
        print(f"BLAD: {exc}", file=sys.stderr)
        return EXIT_FAIL
    print(
        f"ADV n_gold={payload['n_gold_adv']} (T={payload['n_gold_T']} LOC={payload['n_gold_LOC']}) "
        f"acc={payload['accuracy_coarse']:.4f}"
    )
    print(f"  pred_coarse={payload['pred_coarse_on_gold_adv']}")
    log_run(
        task="T-014",
        status="done",
        config_hash=config.config_hash(),
        artifacts=[rel_to_repo(ADV_DIAGNOSIS_PATH), "SOURCES.md"],
        metrics={
            "n_gold_adv": payload["n_gold_adv"],
            "n_gold_T": payload["n_gold_T"],
            "n_gold_LOC": payload["n_gold_LOC"],
            "adv_accuracy_coarse": payload["accuracy_coarse"],
        },
        note="T-014 dopisek: diagnostyka kubełka ADV (N i przyklady pomyłek).",
    )
    return EXIT_OK


def cmd_build_handoff(args: argparse.Namespace) -> int:
    from src.handoff.pack_h1 import pack_h1
    from src.handoff.pack_h1b import pack_h1b
    from src.utils.runs import log_run

    job = (getattr(args, "job", None) or "H1").upper()
    config = _load(args)
    out = Path(args.out) if getattr(args, "out", None) else Path("handoff") / job
    if job == "H1B":
        summary = pack_h1b(config, out_dir=out)
        print(f"zapisano {rel_to_repo(out)}")
        print(f"  parent_jobid={summary['parent_jobid']} --time={summary['job_time']}")
        print("  approved_for_sbatch=true  resume *.done")
        log_run(
            task="T-015",
            status="failed",
            config_hash=config.config_hash(),
            artifacts=["logs/tag_ctrl_1066297.out"],
            metrics={"jobid": 1066297, "n_done": 87, "n_input_books": 965},
            note=(
                "1066297 padl BrokenPipeError przy zapisie parquet (Lustre). "
                "87/965 par na dysku. Successor: H1b."
            ),
            host="cluster",
        )
        log_run(
            task="H1b",
            status="awaiting_cluster",
            config_hash=config.config_hash(),
            artifacts=[
                "handoff/H1b/README.md",
                "handoff/H1b/job.sbatch",
                "handoff/H1b/inputs.manifest.json",
                "handoff/H1b/expected_outputs.json",
                "handoff/H1b/status.json",
            ],
            metrics={
                "approved_for_sbatch": 1,
                "parent_jobid": int(summary["parent_jobid"]),
            },
            note=(
                "H1b: restart T-015 po 1066297 BrokenPipeError (87/965). "
                "Retry parquet + tabulate. Nie ruszono handoff/H1/."
            ),
        )
        return EXIT_OK
    if job != "H1":
        print(f"NIEZAIMPLEMENTOWANE: handoff {job} (H2/H3 pozniej).", file=sys.stderr)
        return EXIT_NOT_IMPLEMENTED
    summary = pack_h1(config, out_dir=out)
    print(f"zapisano {rel_to_repo(out)}")
    print(f"  n_input_files={summary['n_input_files']} n_tokens={summary['n_tokens']}")
    print("  approved_for_sbatch=false  --time w job.sbatch = <Z_PILOTAZU>")
    log_run(
        task="H1",
        status="done",
        config_hash=config.config_hash(),
        artifacts=[
            "handoff/H1/README.md",
            "handoff/H1/dryrun.sbatch",
            "handoff/H1/job.sbatch",
            "handoff/H1/inputs.manifest.json",
            "handoff/H1/expected_outputs.json",
        ],
        metrics={
            "n_input_files": summary["n_input_files"],
            "n_tokens": summary["n_tokens"] or 0,
            "approved_for_sbatch": 0,
        },
        note=(
            "Paczka H1 przygotowana, NIE zatwierdzona do sbatch. "
            "Najpierw dryrun.sbatch (pilot 400k BERT), potem --time w job.sbatch."
        ),
    )
    return EXIT_OK


def cmd_verify_handoff(args: argparse.Namespace) -> int:
    from src.handoff.pack_h1 import H1_DIR, verify_h1
    from src.paths import DATA_INTERIM_DIR
    from src.utils.runs import log_run

    job = (getattr(args, "job", None) or "H1").upper()
    if job != "H1":
        print(f"NIEZAIMPLEMENTOWANE: verify {job}.", file=sys.stderr)
        return EXIT_NOT_IMPLEMENTED
    errors = verify_h1(out_dir=H1_DIR, strict=bool(getattr(args, "strict", False)))
    if errors:
        for err in errors:
            print(f"HANDOFF {job}: {err}", file=sys.stderr)
        return EXIT_FAIL
    tagged = DATA_INTERIM_DIR / "ctrl_tagged"
    n_parquet = len(list(tagged.glob("*.parquet"))) if tagged.is_dir() else 0
    print(f"HANDOFF {job}: paczka kompletna")
    print(f"  ctrl_tagged parquet={n_parquet}")
    log_run(
        task="H1",
        status="done",
        config_hash=_load(args).config_hash(),
        artifacts=["data/interim/ctrl_tagged/", "handoff/H1b/status.json"],
        metrics={"n_parquet": n_parquet, "verify_strict": 1},
        note="make handoff-verify JOB=H1 — H1b successor, artefakty z klastra OK.",
    )
    return EXIT_OK


def cmd_figs_smoke(args: argparse.Namespace) -> int:
    from src.utils.runs import log_run
    from src.viz.fig00_smoke import run as run_smoke

    config = _load(args)
    saved = run_smoke(config)
    artifacts = [rel_to_repo(p) for p in (saved.png, saved.svg, saved.json, saved.index)]
    for path in artifacts:
        print(f"zapisano {path}")

    log_run(
        task="T-008",
        status="done",
        config_hash=config.config_hash(),
        artifacts=artifacts,
        metrics={"n_files": 3},
        note="make figs-smoke",
    )
    return EXIT_OK


def cmd_freeze(args: argparse.Namespace) -> int:
    """`make freeze` musi zawiesc, jesli `make gates` nie byl uruchomiony
    na aktualnym configu (08_REPO.md §6)."""
    config = _load(args)
    gates_path = RESULTS_DIR / "gates.json"

    if not gates_path.exists():
        print(
            "BLOCKED: brak results/gates.json. FREEZE (T-033) wymaga wczesniejszego "
            "`make gates` (T-029..T-032) na aktualnym configu.",
            file=sys.stderr,
        )
        return EXIT_FAIL

    from src.utils.io import read_json

    gates = read_json(gates_path)
    if gates.get("config_hash") != config.config_hash():
        print(
            "BLOCKED: results/gates.json pochodzi z innego configu "
            f"({gates.get('config_hash')} != {config.config_hash()}). "
            "Uruchom `make gates` ponownie.",
            file=sys.stderr,
        )
        return EXIT_FAIL

    raise StageNotImplementedError("T-033 (P4)")


def cmd_main(args: argparse.Namespace) -> int:
    """`make main` musi zawiesc bez configs/frozen/ (AGENTS.md zasada 2)."""
    frozen = sorted(FROZEN_CONFIG_DIR.glob("*.yaml")) if FROZEN_CONFIG_DIR.exists() else []
    if not frozen:
        print(
            "BLOCKED: configs/frozen/ jest puste. Nie wolno liczyc niczego na Koranie "
            "przed FREEZE (T-033). Uruchom najpierw `make gates`, potem `make freeze`.",
            file=sys.stderr,
        )
        return EXIT_FAIL
    raise StageNotImplementedError("T-034..T-042 (P5)")


def cmd_pending(args: argparse.Namespace) -> int:
    raise StageNotImplementedError(PENDING_STAGES[args.command])


# --------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------


def _add_config_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="sciezka do configu bazowego")
    parser.add_argument(
        "--overlay",
        action="append",
        default=[],
        help="nakladka na config (mozna podac wielokrotnie, kolejnosc ma znaczenie)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="quran-stylometry — CLI. Kolejnosc etapow: docs/08_REPO.md §6.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_hash = sub.add_parser("hash-config", help="deterministyczny sha256 zwalidowanego configu")
    _add_config_args(p_hash)
    p_hash.set_defaults(func=cmd_hash_config)

    p_show = sub.add_parser("show-config", help="zwalidowany config jako kanoniczny JSON")
    _add_config_args(p_show)
    p_show.set_defaults(func=cmd_show_config)

    p_env = sub.add_parser("init-env", help="tworzy configs/env.local.yaml (HOST_ROLE=laptop)")
    p_env.add_argument("--path", default=None)
    p_env.add_argument("--force", action="store_true")
    p_env.set_defaults(func=cmd_init_env)

    p_vs = sub.add_parser("verify-sources", help="sprawdza zrodla z 09_DECISIONS §2")
    _add_config_args(p_vs)
    p_vs.add_argument("--sources", default=str(DEFAULT_SOURCES))
    p_vs.add_argument("--out", default=str(SOURCE_CHECK_PATH))
    p_vs.set_defaults(func=cmd_verify_sources)

    p_smoke = sub.add_parser("figs-smoke", help="generuje figure testowa z pelnym kompletem plikow")
    _add_config_args(p_smoke)
    p_smoke.set_defaults(func=cmd_figs_smoke)

    p_eqtb = sub.add_parser("download-eqtb", help="T-009: pobranie + parsowanie EQTB")
    _add_config_args(p_eqtb)
    p_eqtb.add_argument("--force", action="store_true", help="wymusza ponowne pobranie/ekstrakcje")
    p_eqtb.set_defaults(func=cmd_download_eqtb)

    p_qac = sub.add_parser(
        "formalize-qac-fallback",
        help="T-010: formalizacja fallbacku QAC (bez pobierania)",
    )
    _add_config_args(p_qac)
    p_qac.set_defaults(func=cmd_formalize_qac_fallback)

    p_ctrl = sub.add_parser("select-ctrl", help="T-011: selekcja autorow OpenITI (§3)")
    _add_config_args(p_ctrl)
    p_ctrl.add_argument("--workers", type=int, default=8)
    p_ctrl.add_argument(
        "--skip-download", action="store_true", help="nie pobieraj tekstow wybranych"
    )
    p_ctrl.set_defaults(func=cmd_select_ctrl)

    p_norm = sub.add_parser("normalize", help="T-013: normalizator arabskiego (strict/light)")
    _add_config_args(p_norm)
    p_norm.set_defaults(func=cmd_normalize)

    p_cap = sub.add_parser(
        "cap-ctrl",
        help="T-013b: limit 200k tokenow per autor (proporcjonalnie, losowy span)",
    )
    _add_config_args(p_cap)
    p_cap.set_defaults(func=cmd_cap_ctrl)

    p_tag = sub.add_parser(
        "tag",
        help="T-014 ewaluacja Koran (domyslnie) albo T-015 --corpus ctrl (klaster)",
    )
    _add_config_args(p_tag)
    p_tag.add_argument("--corpus", choices=["quran", "ctrl"], default="quran")
    p_tag.add_argument("--eqtb", default=None, help="sciezka do eqtb_tokens.parquet")
    p_tag.add_argument("--out", default=None, help="sciezka results/tagger_eval.json")
    p_tag.add_argument(
        "--max-words",
        type=int,
        default=None,
        help="obciecie do testow, nie pelny T-014",
    )
    p_tag.add_argument("--skip-fig", action="store_true")
    p_tag.add_argument("--input", default=None, help="katalog ctrl_capped (T-015)")
    p_tag.add_argument("--output", default=None, help="katalog ctrl_tagged (T-015)")
    p_tag.add_argument("--disambiguator", default=None, choices=["mle", "bert"])
    p_tag.add_argument("--batch-size", type=int, default=64)
    p_tag.add_argument("--checkpoint-every", type=int, default=200)
    p_tag.add_argument("--limit-tokens", type=int, default=None)
    p_tag.add_argument("--pilot", action="store_true")
    p_tag.set_defaults(func=cmd_tag)

    p_tag_ctrl = sub.add_parser("tag-ctrl", help="T-015: alias --corpus ctrl (klaster)")
    _add_config_args(p_tag_ctrl)
    p_tag_ctrl.add_argument("--input", default=None)
    p_tag_ctrl.add_argument("--output", default=None)
    p_tag_ctrl.add_argument("--disambiguator", default="bert", choices=["mle", "bert"])
    p_tag_ctrl.add_argument("--batch-size", type=int, default=64)
    p_tag_ctrl.add_argument("--checkpoint-every", type=int, default=200)
    p_tag_ctrl.add_argument("--limit-tokens", type=int, default=None)
    p_tag_ctrl.add_argument("--pilot", action="store_true")
    p_tag_ctrl.set_defaults(func=cmd_tag_ctrl, corpus="ctrl")

    p_adv = sub.add_parser("diagnose-adv", help="T-014: diagnostyka kubełka ADV")
    _add_config_args(p_adv)
    p_adv.set_defaults(func=cmd_diagnose_adv)

    p_quotes = sub.add_parser("clean-quotes", help="T-016: cytaty Koranu w CTRL (nie T-017)")
    _add_config_args(p_quotes)
    p_quotes.add_argument("--eqtb", default=None)
    p_quotes.add_argument("--input", default=None, help="katalog ctrl_capped")
    p_quotes.add_argument("--output", default=None, help="katalog openiti_clean")
    p_quotes.add_argument("--limit-books", type=int, default=None)
    p_quotes.add_argument("--skip-fuzzy", action="store_true")
    p_quotes.add_argument("--skip-fig", action="store_true")
    p_quotes.set_defaults(func=cmd_clean_quotes)

    p_dedup = sub.add_parser("dedup", help="T-017: redundancja wewnetrzna 7-gramow")
    _add_config_args(p_dedup)
    p_dedup.add_argument("--input", default=None, help="katalog openiti_clean")
    p_dedup.add_argument("--limit-books", type=int, default=None)
    p_dedup.add_argument("--skip-fig", action="store_true")
    p_dedup.add_argument("--skip-write-dedup", action="store_true")
    p_dedup.set_defaults(func=cmd_dedup)

    p_seg = sub.add_parser("segment", help="T-019: okna (nie T-020)")
    _add_config_args(p_seg)
    p_seg.add_argument("--input", default=None, help="katalog openiti_clean")
    p_seg.add_argument("--limit-books", type=int, default=None)
    p_seg.add_argument("--sizes", default=None, help="np. 400 albo 250,400,800")
    p_seg.add_argument("--skip-olap", action="store_true")
    p_seg.set_defaults(func=cmd_segment)

    p_splits = sub.add_parser("splits", help="T-020: splity CTRL po author_id")
    _add_config_args(p_splits)
    p_splits.add_argument("--skip-windows", action="store_true")
    p_splits.set_defaults(func=cmd_splits)

    p_feat = sub.add_parser("features", help="T-021 F1 / T-022 F2 / T-023 F3 (inne: T-024+)")
    _add_config_args(p_feat)
    p_feat.add_argument("--family", default="character")
    p_feat.add_argument("--skip-fig", action="store_true")
    p_feat.add_argument("--limit", type=int, default=None, help="obciecie okien do testow")
    p_feat.set_defaults(func=cmd_features)

    p_chrono_table = sub.add_parser(
        "chronology", help="T-018: zgodnosc chronologii + FIG-06b (nie T-043 chrono)"
    )
    _add_config_args(p_chrono_table)
    p_chrono_table.add_argument("--skip-fig", action="store_true")
    p_chrono_table.set_defaults(func=cmd_chronology)

    p_h1 = sub.add_parser("build-handoff", help="przygotuj paczke handoff/H1 (bez sbatch)")
    _add_config_args(p_h1)
    p_h1.add_argument("--job", default="H1")
    p_h1.add_argument("--out", default=None)
    p_h1.set_defaults(func=cmd_build_handoff)

    p_vh = sub.add_parser("verify-handoff", help="sprawdz paczke / powrot H1")
    _add_config_args(p_vh)
    p_vh.add_argument("--job", default="H1")
    p_vh.add_argument("--strict", action="store_true")
    p_vh.set_defaults(func=cmd_verify_handoff)

    p_freeze = sub.add_parser("freeze", help="T-033 FREEZE (wymaga wczesniejszego `make gates`)")
    _add_config_args(p_freeze)
    p_freeze.set_defaults(func=cmd_freeze)

    p_main = sub.add_parser("main", help="wynik glowny (wymaga configs/frozen/)")
    _add_config_args(p_main)
    p_main.set_defaults(func=cmd_main)

    for stage in PENDING_STAGES:
        if stage in {"freeze", "main"}:
            continue
        p_stage = sub.add_parser(stage, help=f"etap zaplanowany: {PENDING_STAGES[stage]}")
        _add_config_args(p_stage)
        p_stage.add_argument("--job", default=None)
        p_stage.add_argument("--out", default=None)
        p_stage.add_argument("--strict", action="store_true")
        p_stage.set_defaults(func=cmd_pending)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    ensure_dir(RESULTS_DIR)
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except StageNotImplementedError as exc:
        print(
            f"NIEZAIMPLEMENTOWANE: etap '{args.command}' nalezy do {exc}. "
            "Zakres tej fazy: docs/07_TASKS.md.",
            file=sys.stderr,
        )
        return EXIT_NOT_IMPLEMENTED


if __name__ == "__main__":
    raise SystemExit(main())
