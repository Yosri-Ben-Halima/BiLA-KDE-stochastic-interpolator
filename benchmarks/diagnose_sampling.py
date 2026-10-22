"""Bounded deterministic profiling of the previously timed-out AR-gap fit."""

import argparse
import cProfile
import io
import json
import os
import pstats
from pathlib import Path

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

from benchmarks.scenarios import generate, seed_for
from bilakde.bridge import _fit
from bilakde.config import SamplingConfig
from bilakde.errors import BridgeError
from bilakde.resources import Budget


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    case = {
        "id": "smoke-ar_gaussian-gap30",
        "scenario": "ar_gaussian",
        "missing": 30,
        "replicate": 0,
        "partition": "smoke",
    }
    series, _ = generate(case, 2026)
    seed = seed_for(2026, case["id"], "bila")
    config = SamplingConfig(
        time_limit_seconds=60, max_draws_per_chain=2000, stopping="fixed_iterations"
    )
    budget = Budget(config)
    profile = cProfile.Profile()
    profile.enable()
    try:
        result = _fit(series, (100, 100), seed, 8000, config, budget=budget)
        evidence = {"status": "success", "diagnostics": result.diagnostics}
    except BridgeError as exc:
        evidence = {"status": exc.status, "reason": exc.reason, "diagnostics": exc.diagnostics}
    finally:
        profile.disable()
    buffer = io.StringIO()
    pstats.Stats(profile, stream=buffer).strip_dirs().sort_stats("cumulative").print_stats(30)
    (args.output / "profile.txt").write_text(buffer.getvalue(), encoding="utf-8")
    evidence["budget"] = budget.evidence()
    (args.output / "result.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence["budget"]))
    print(buffer.getvalue())


if __name__ == "__main__":
    main()
