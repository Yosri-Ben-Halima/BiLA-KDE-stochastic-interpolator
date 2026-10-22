"""Fixed three-seed tail investigation, including independent exact-mixture draws."""

import argparse
import itertools
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from scipy.special import logsumexp, ndtr

from benchmarks.oracles import reference_case
from benchmarks.runner import source_signature, write_json
from bilakde.config import SamplingConfig
from bilakde.diagnostics import quantile_mcse
from bilakde.errors import BridgeError
from bilakde.resources import Budget


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--elliptical-only",
        action="store_true",
        help="Reproduce the original transition as a diagnostic ablation",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    signature = source_signature()
    T, end, n = 4, 2 * np.sqrt(5), 32000
    mu = np.array(list(itertools.product([-1.0, 1.0], repeat=T)))
    log_weights = -0.5 * (end - mu.sum(axis=1)) ** 2
    weights = np.exp(log_weights - logsumexp(log_weights))
    means = np.cumsum(mu, axis=1)[:, :-1] + np.arange(1, T) / T * (end - mu.sum(axis=1))[:, None]
    covariance = 0.25 * (
        np.minimum.outer(np.arange(1, T), np.arange(1, T))
        - np.outer(np.arange(1, T), np.arange(1, T)) / T
    )
    expected_mean = weights @ means
    variance = np.diag(covariance) + weights @ (means - expected_mean) ** 2
    exact = np.array(
        [
            [
                brentq(
                    lambda x, j=j, p=p: (
                        float(weights @ ndtr((x - means[:, j]) / np.sqrt(covariance[j, j]))) - p
                    ),
                    -8,
                    12,
                )
                for j in range(T - 1)
            ]
            for p in (0.025, 0.975)
        ]
    )
    rows = []
    for seed in (2026, 2027, 2028):
        rng = np.random.default_rng(seed)
        labels = rng.choice(len(weights), n, p=weights)
        iid = means[labels] + rng.normal(size=(n, T - 1)) @ np.linalg.cholesky(covariance).T
        iid = iid.reshape(4, n // 4, T - 1)
        errors = np.abs(np.quantile(iid, [0.025, 0.975], axis=(0, 1)) - exact) / np.sqrt(variance)
        mcse = np.array([quantile_mcse(iid, p) for p in (0.025, 0.975)]) / np.sqrt(variance)
        iid_pass = bool(np.all(errors + 2 * mcse <= 0.15))
        config = SamplingConfig(time_limit_seconds=60)
        try:
            result = reference_case(
                {
                    "kind": "mixture",
                    "T": 4,
                    "z": 2,
                    "n_samples": n,
                    "transition": "elliptical_only" if args.elliptical_only else "hybrid",
                },
                seed,
                config,
                budget=Budget(config),
            )
            row = {"seed": seed, "status": "success", "diagnostics": result["diagnostics"]}
        except BridgeError as exc:
            row = {"seed": seed, "status": exc.status, "diagnostics": exc.diagnostics}
        row.update(iid_pass=iid_pass, iid_tail_errors=errors, iid_tail_mcse=mcse)
        rows.append(row)
        write_json(args.output / "results.json", {"source_signature": signature, "results": rows})
        print(seed, row["status"], "iid", iid_pass, flush=True)


if __name__ == "__main__":
    main()
