import time
from dataclasses import asdict
from importlib.metadata import version

import numpy as np

from .config import SamplingConfig, validate_request
from .density import InnovationModel
from .diagnostics import assess
from .errors import BridgeInputError, SamplingError
from .inputs import prepare
from .resources import run_guarded
from .results import BridgeResult
from .sampling import elliptical_sample


def _fit(series, window_size, seed, n_samples, config, mode="linear", budget=None):
    gap = prepare(series, window_size)
    budget.check()
    d = gap.T - 1
    budget.preflight(
        8 * (10 * d * d + 12 * n_samples * d + sum(window_size) * 8 + 8 * gap.T * sum(window_size))
    )
    if not np.isfinite(gap.b - gap.a):
        raise BridgeInputError("invalid_input", "endpoint displacement overflows float64")
    model = InnovationModel(gap.left, gap.right, gap.T, mode)
    budget.preflight(8 * 32 * model.T * (len(model.left.data) + len(model.right.data)))
    reference = model.reference(gap.b - gap.a)
    states, diagnostics = elliptical_sample(
        lambda x: model.target(x, gap.b - gap.a),
        reference,
        seed,
        n_samples,
        config,
        budget,
        refresh=model.conditional_refresh,
    )
    chains = np.concatenate(
        [
            np.full((4, n_samples // 4, 1), gap.a),
            gap.a + states,
            np.full((4, n_samples // 4, 1), gap.b),
        ],
        axis=-1,
    )
    tolerance = 1e-10 * max(1, abs(gap.a), abs(gap.b))
    sum_error = float(np.max(np.abs(np.diff(chains, axis=-1).sum(axis=-1) - (gap.b - gap.a))))
    endpoint_error = float(
        max(np.abs(chains[:, :, 0] - gap.a).max(), np.abs(chains[:, :, -1] - gap.b).max())
    )
    if not np.isfinite(chains).all() or max(sum_error, endpoint_error) > tolerance:
        raise SamplingError(
            "numerical_failure", "returned path fails endpoint/sum invariants", diagnostics
        )
    # Offset addition can quantize away variation even when the centered draws
    # mixed correctly. Certify the actual representable returned paths.
    returned_diagnostics = assess(chains[:, :, 1:-1] - gap.a, gap.b - gap.a)
    budget.check()
    if not returned_diagnostics["diagnostics_pass"]:
        raise SamplingError(
            "numerical_failure",
            "returned level precision invalidates diagnostics",
            {**diagnostics, **returned_diagnostics},
        )
    diagnostics.update(returned_diagnostics)
    diagnostics.update(
        seed=int(seed),
        config=asdict(config),
        density=model.metadata(),
        endpoint_error=endpoint_error,
        increment_sum_error=sum_error,
        support_z=float((gap.b - gap.a - model.means.sum()) / np.sqrt(model.variances.sum())),
        gap_start=gap.start,
        gap_stop=gap.stop,
        selected_left=[gap.start - 1 - window_size[0], gap.start - 1],
        selected_right=[gap.stop, gap.stop + window_size[1]],
        versions={name: version(name) for name in ("numpy", "scipy", "pandas", "arviz")},
        uncertainty="path conditional on fitted KDEs; excludes density-estimation uncertainty",
    )
    budget.check()
    diagnostics.update(budget.evidence())
    return BridgeResult(gap, chains, diagnostics)


class BiLAKDEBridge:
    def __init__(self, window_size=100, random_state=None, sampling=None):
        self.sampling = SamplingConfig() if sampling is None else sampling
        self.window_size = validate_request(window_size, random_state, 2000, self.sampling)
        self.random_state = random_state

    def fit_transform(self, series, n_samples=2000):
        started = time.perf_counter()
        validate_request(self.window_size, self.random_state, n_samples, self.sampling)
        seed = self.random_state
        if seed is None:
            seed = int(np.random.SeedSequence().generate_state(1, dtype=np.uint64)[0])
        return run_guarded(
            _fit, (series, self.window_size, seed, n_samples, self.sampling), self.sampling, started
        )
