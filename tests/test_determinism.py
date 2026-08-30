"""T-004 — dwa przebiegi tego samego pipeline'u daja ten sam hash wyjscia.

Pipeline jest tu syntetyczny i celowo maly: w P0 nie ma danych, a pelny test
end-to-end na zredukowanym podzbiorze to T-051. Chodzi o to, zeby juz teraz
kazda przyszla warstwa losowa miala gotowy kontrakt: `new_rng(seed, stream)`
i porownanie hasha artefaktu, a nie "wyglada tak samo".
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import numpy as np

from src.config import Config
from src.paths import REPO_ROOT
from src.utils.hashing import sha256_json
from src.utils.seed import new_rng, set_all_seeds


def _mini_pipeline(seed: int) -> dict[str, object]:
    """Imituje ksztalt prawdziwego etapu: seed -> losowanie -> agregat -> artefakt."""
    set_all_seeds(seed)
    rng = new_rng(seed, stream="test_determinism")
    sample = rng.normal(size=256)
    weights = rng.permutation(sample.size)
    return {
        "mean": float(np.mean(sample)),
        "median": float(np.median(sample)),
        "weighted": float(np.dot(sample, weights) / weights.sum()),
        "first_five": [float(x) for x in sample[:5]],
        "perm_head": [int(x) for x in weights[:5]],
    }


def test_two_runs_produce_identical_output_hash(config: Config) -> None:
    first = _mini_pipeline(config.seed)
    second = _mini_pipeline(config.seed)
    assert sha256_json(first) == sha256_json(second)


def test_different_seed_produces_different_output(config: Config) -> None:
    assert sha256_json(_mini_pipeline(config.seed)) != sha256_json(_mini_pipeline(config.seed + 1))


def test_streams_are_independent(config: Config) -> None:
    """Dolozenie nowego etapu nie moze przesunac losowan w etapach juz policzonych."""
    a = new_rng(config.seed, stream="variance").normal(size=32)
    b = new_rng(config.seed, stream="permutations").normal(size=32)
    assert not np.allclose(a, b)
    # Ten sam strumien odtwarza sie identycznie.
    assert np.array_equal(a, new_rng(config.seed, stream="variance").normal(size=32))


def test_set_all_seeds_reports_pythonhashseed() -> None:
    report = set_all_seeds(20260830)
    assert report.seed == 20260830
    assert report.libraries["numpy"] == "seeded"
    assert report.libraries["random"] == "seeded"
    # Raport ma byc uczciwy: jesli PYTHONHASHSEED nie jest "0", ma to byc widac.
    assert report.pythonhashseed_ok == (report.pythonhashseed == "0")


def test_determinism_holds_across_processes() -> None:
    """Ten sam pipeline w dwoch osobnych procesach = ten sam hash."""
    script = textwrap.dedent("""
        import numpy as np
        from src.utils.hashing import sha256_json
        from src.utils.seed import new_rng, set_all_seeds

        set_all_seeds(20260830)
        rng = new_rng(20260830, stream="test_determinism")
        sample = rng.normal(size=256)
        weights = rng.permutation(sample.size)
        print(sha256_json({
            "mean": float(np.mean(sample)),
            "weighted": float(np.dot(sample, weights) / weights.sum()),
            "perm_head": [int(x) for x in weights[:5]],
        }))
        """)
    outputs = set()
    for hashseed in ("0", "7"):
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PYTHONHASHSEED": hashseed},
        )
        outputs.add(completed.stdout.strip())
    assert len(outputs) == 1, f"Hash rozni sie miedzy procesami: {outputs}"
