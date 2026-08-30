"""T-002 — `config_hash` musi byc deterministyczny.

Test pilnuje trzech wlasciwosci, bez ktorych hash nie nadaje sie do znakowania
artefaktow: niezaleznosci od formatowania YAML, niezaleznosci od `PYTHONHASHSEED`
(sprawdzane w osobnym procesie) i wrazliwosci na kazda zmiane wartosci.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from src.config import Config, deep_merge, load_config, load_env_local
from src.paths import CONFIGS_DIR, REPO_ROOT
from src.utils.hashing import canonical_json, sha256_json


def test_hash_is_stable_within_process(config: Config) -> None:
    assert config.config_hash() == Config().config_hash()


def test_hash_ignores_yaml_key_order(tmp_path: Path) -> None:
    payload = load_config(CONFIGS_DIR / "base.yaml").hashable_payload()

    forward = tmp_path / "forward.yaml"
    reverse = tmp_path / "reverse.yaml"
    forward.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
    reverse.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    assert load_config(forward).config_hash() == load_config(reverse).config_hash()


def test_hash_ignores_whitespace_and_comments(tmp_path: Path, base_config_path: Path) -> None:
    original = base_config_path.read_text(encoding="utf-8")
    noisy = tmp_path / "noisy.yaml"
    noisy.write_text("# komentarz\n\n\n" + original + "\n\n", encoding="utf-8")

    assert load_config(noisy).config_hash() == load_config(base_config_path).config_hash()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("seed", 1),
        ("experiments_skip", ["E-14"]),
    ],
)
def test_hash_changes_when_value_changes(config: Config, field: str, value: object) -> None:
    changed = config.model_copy(update={field: value})
    assert changed.config_hash() != config.config_hash()


def test_nested_value_change_propagates_to_hash(config: Config) -> None:
    changed = config.model_copy(
        update={"tagger": config.tagger.model_copy(update={"version": "inna-wersja"})}
    )
    assert changed.config_hash() != config.config_hash()


def test_host_role_is_outside_config_hash(tmp_path: Path) -> None:
    """HOST_ROLE nie moze wplywac na hash — inaczej laptop i klaster licza rozne."""
    env_path = tmp_path / "env.local.yaml"
    env_path.write_text("host_role: cluster\n", encoding="utf-8")

    assert load_env_local(env_path).host_role == "cluster"
    assert "host_role" not in canonical_json(Config().hashable_payload())


def test_hash_is_stable_across_processes_and_hashseeds(base_config_path: Path) -> None:
    """Uruchamia liczenie hasha w podprocesach o roznym PYTHONHASHSEED.

    Randomizacja hasha stringow w CPythonie jest najczestszym zrodlem "hash
    zmienil sie miedzy przebiegami" — jesli gdzies w lancuchu wkradnie sie
    iteracja po zbiorze, ten test to wylapie.
    """
    script = textwrap.dedent(f"""
        from src.config import load_config
        print(load_config(r"{base_config_path}").config_hash())
        """)
    hashes = set()
    for hashseed in ("0", "1", "12345"):
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PYTHONHASHSEED": hashseed},
        )
        hashes.add(completed.stdout.strip())
    assert len(hashes) == 1, f"Hash zalezy od PYTHONHASHSEED: {hashes}"


def test_unknown_key_is_rejected(tmp_path: Path, base_config_path: Path) -> None:
    """Literowka w nazwie parametru musi zostac zauwazona, nie zignorowana."""
    broken = tmp_path / "broken.yaml"
    broken.write_text(
        base_config_path.read_text(encoding="utf-8") + "\nwindow_sizee: 400\n", encoding="utf-8"
    )
    with pytest.raises(Exception, match="window_sizee"):
        load_config(broken)


def test_deep_merge_overlay_wins_at_leaf_level() -> None:
    base = {"a": {"b": 1, "c": 2}, "d": 3}
    overlay = {"a": {"c": 99}}
    assert deep_merge(base, overlay) == {"a": {"b": 1, "c": 99}, "d": 3}


def test_laptop_only_overlay_changes_hash(base_config_path: Path) -> None:
    plain = load_config(base_config_path)
    with_overlay = load_config(base_config_path, overlays=[CONFIGS_DIR / "laptop_only.yaml"])
    assert with_overlay.config_hash() != plain.config_hash()
    assert with_overlay.corpus.min_tokens_per_author == 20000
    # Minimum liczby autorow jest twarde nawet w sciezce bez klastra.
    assert with_overlay.corpus.min_authors == 60


def test_canonical_json_sorts_keys() -> None:
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'
    assert sha256_json({"b": 1, "a": 2}) == sha256_json({"a": 2, "b": 1})


def test_frozen_parameters_match_decisions(base_config_path: Path) -> None:
    """Wartosci z docs/09_DECISIONS.md §6 sa zamrozone — test broni ich przed dryfem."""
    cfg = load_config(base_config_path)
    assert cfg.seed == 20260830
    assert cfg.segmentation.window_size == 400
    assert cfg.segmentation.overlap == 0.0
    assert cfg.segmentation.overlap_local == 0.5
    assert cfg.segmentation.min_tail_ratio == 0.6
    assert cfg.segmentation.max_window_ratio == 1.6
    assert cfg.corpus.min_authors == 60
    assert cfg.corpus.min_tokens_per_author == 30000
    assert cfg.corpus.min_works_per_author == 2
    assert cfg.variance.bootstrap_B == 200
    assert cfg.significance.permutations == 10000
    assert cfg.features.mfw_grid == [100, 300, 1000, 3000]
    assert cfg.features.char_ngram_range == [3, 5]
    assert cfg.features.char_max_features == 50000
    assert cfg.quotes.quote_ngram_n == 7
    assert cfg.quotes.minhash_num_perm == 128
    assert cfg.quotes.minhash_threshold == 0.8
    assert cfg.gates.domain_probe_auc_max == 0.98
    assert cfg.gates.av_ood_eer_max == 0.35
    assert cfg.av.pairs_max_per_split == 400000
    assert cfg.av.hard_negative_ratio == 0.7
