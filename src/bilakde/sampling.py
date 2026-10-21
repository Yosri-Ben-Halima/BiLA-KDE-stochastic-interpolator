"""Elliptical slice sampling in free interior-level coordinates."""

import numpy as np

from .diagnostics import assess
from .errors import SamplingError


def elliptical_sample(target, reference, seed, n_samples, config, budget, refresh=None):
    count = n_samples // 4
    dimension = len(reference.mean)
    budget.preflight(8 * (8 * dimension * dimension + 12 * count * dimension))
    streams = np.random.SeedSequence(seed).spawn(4)
    rngs = [np.random.default_rng(s) for s in streams]

    def normal():
        return np.stack([r.normal(size=dimension) for r in rngs])

    states = reference.mean + 2 * normal() @ reference.cholesky.T
    ratio = target(states) - reference.logpdf(states)
    if not np.isfinite(ratio).all():
        raise SamplingError("numerical_failure", "nonfinite initial target/reference ratio")
    ring = np.empty((4, count, dimension))
    evaluations = 4
    diagnostic = {}
    for step in range(500 + config.max_draws_per_chain):
        budget.check()
        prior_noise = normal() @ reference.cholesky.T
        height = ratio + np.log([r.uniform() for r in rngs])
        angles = np.array([r.uniform(0, 2 * np.pi) for r in rngs])
        low, high = angles - 2 * np.pi, angles.copy()
        active = np.ones(4, dtype=bool)
        original = states.copy()
        for _ in range(256):
            budget.check()
            candidate = reference.mean + (original - reference.mean) * np.cos(angles[:, None])
            candidate += prior_noise * np.sin(angles[:, None])
            candidate_ratio = target(candidate) - reference.logpdf(candidate)
            evaluations += 4
            if np.isnan(candidate_ratio).any() or np.isposinf(candidate_ratio).any():
                raise SamplingError("numerical_failure", "invalid target evaluation", diagnostic)
            accept = active & (candidate_ratio >= height)
            states[accept] = candidate[accept]
            ratio[accept] = candidate_ratio[accept]
            active[accept] = False
            if not active.any():
                break
            low = np.where(active & (angles < 0), angles, low)
            high = np.where(active & (angles >= 0), angles, high)
            angles = np.array(
                [
                    r.uniform(a, b) if enabled else angle
                    for r, a, b, enabled, angle in zip(rngs, low, high, active, angles)
                ]
            )
        else:
            raise SamplingError("numerical_failure", "angular bracket update limit", diagnostic)
        if refresh is not None:
            # Kernel labels and increments can remain correlated for narrow KDE
            # bandwidths. Several cheap Gibbs sweeps complement the global move.
            for _ in range(4):
                budget.check()
                states = refresh(states, reference.end, rngs)
            ratio = target(states) - reference.logpdf(states)
            evaluations += 4
            if not np.isfinite(ratio).all():
                raise SamplingError(
                    "numerical_failure", "nonfinite refreshed target/reference ratio"
                )
        if step < 500:
            continue
        retained = step - 499
        ring[:, (retained - 1) % count] = states
        final = retained == config.max_draws_per_chain
        check = (
            retained >= count
            and (final or retained % 250 == 0)
            and (config.stopping == "diagnostics" or final)
        )
        if not check:
            continue
        order = (np.arange(count) + retained % count) % count
        block = ring[:, order].copy()
        diagnostic = assess(block, reference.end)
        budget.check()
        diagnostic.update(
            warmup_per_chain=500,
            draws_per_chain=count,
            total_retained_updates_per_chain=retained,
            discarded_draws_per_chain=retained - count,
            target_evaluations=evaluations,
            transition_kernel="elliptical_slice"
            if refresh is None
            else "elliptical_slice+kernel_gibbs",
            gibbs_sweeps_per_update=0 if refresh is None else 4,
            chain_streams=[list(s.spawn_key) for s in streams],
        )
        budget.checkpoint(diagnostic)
        if diagnostic["diagnostics_pass"]:
            return block, dict(diagnostic, **budget.evidence())
    raise SamplingError(
        "draw_limit", "final returned block did not meet diagnostic minima", diagnostic
    )
