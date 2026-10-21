# Updated-sampler validation plan — 20 October 2026

This plan is recorded before executing the new scientific smoke stage. It validates the current sampler; it does not test scientific superiority. No four-hour research campaign is authorized by this step.

## Fixed configuration

Use `benchmarks/validation.toml`: seed 2026; 24,000 predictive samples for every stochastic competitor; 32,000 samples per reference check; exact windows of 100 observed increments per side. Each case retains the 60-second and 2-GiB limits, 500 warmup updates per chain, and 10,000 retained-update cap per chain. The smoke stage remains capped at 30 minutes. Existing stage reservation rules preserve complete method blocks and mark unreached cases explicitly.

The larger ensembles address precision failures seen in the original 2,000-sample smoke stage. They are a declared configuration change, not a revision of the old results. No fallback from 95% to 90% intervals is permitted in this scientific run. All previously required quantile probabilities and diagnostic thresholds remain unchanged. Failures remain visible; this run will not be repeated automatically until it passes.

## Reference evidence

1. Retain the six independent-Gaussian checks (10, 30, 100 missing values; typical and displaced endpoints), four frozen two-component Gaussian-mixture checks, and independent Bayesian reference check.
2. Add four exactly enumerated fitted KDE-mixture bridges (four or six increments; typical/displaced endpoints). Frozen component formulas independently calculate densities and conditional component means/covariances. These checks exercise the actual production `conditional_refresh` kernel composed with elliptical slice sampling. Frozen and production log densities must agree within 1e-10 at deterministic probes.
3. Retain the existing two-Monte-Carlo-SE accuracy screens: maximum standardized mean error <= 0.10, covariance relative error <= 0.15, midpoint CDF probability error <= 0.05, with twice the corresponding MCSE added before acceptance.
4. Add whole-path squared-norm expectation accuracy (relative tolerance 0.15) and 2.5%/97.5% exact marginal quantiles at the first, middle, and last missing coordinates (standard-deviation-scaled tolerance 0.15). Both add twice the corresponding MCSE before acceptance. Exact mixture quantiles are obtained by scalar CDF root finding, independently of sampled quantiles. These finite screens do not establish all path functionals or every tail event.
5. Retain four-chain R-hat <= 1.01, bulk/tail ESS >= 400, mean MCSE/std <= 0.05, finite diagnostics, endpoint invariants, and the prediction output's quantile MCSE/std <= 0.10. Covariance/path-expectation precision is estimated coarsely from four independent chain groups; this limitation remains explicit.

The stage has 15 reference checks and 36 method applications: all twelve methods on the unchanged three smoke fixtures. Software regression tests run first. The exact executed source/configuration signatures and case ordering are recorded by the runner.

## Evidence and acceptance

Write a new directory under `results/step1-20261020/`, preserving all earlier evidence. Respect the requested cleanup preference: this configuration does not save NPZ chains; successful prediction summaries use JSON with observed data, withheld truth, and point estimates. Numerical diagnostics, scores, seeds, configuration, and source hashes remain inspectable. Lack of persisted raw chains limits retrospective reanalysis; a deterministic rerun requires the recorded code and configuration and may differ if it hits a time cap.

The smoke gate remains unchanged: every reference must pass, and every declared method must have at least one complete successful result. A validated smoke is a prerequisite for a later research campaign, not evidence of calibration or superiority. Incomplete results must be reported as incomplete, with the blocking checks identified.

Reproduce with:

```powershell
uv run pytest -q
uv run python benchmarks/run.py --stage smoke --config benchmarks/validation.toml --output results/step1-20261020/smoke
```

## Infrastructure interruption and bounded retry

The first attempt completed eight reference checks successfully, then recorded an elapsed-clock jump during `oracle-mixture-T4-z2`: its worker deadline evidence was 10,811.55 seconds despite a 60-second limit. The overall clock reached 10,874.45 seconds before the runner could stop and mark the remaining 42 cases untested. This is consistent with machine/process suspension; the cause is not independently confirmed. The evidence is preserved unchanged in `results/step1-20261020/smoke/` and is incomplete. The elapsed wall-time overrun must not be described as a completed capped CPU experiment.

One infrastructure retry is declared before execution, with identical source, configuration, fixtures, seeds, accuracy requirements and ordering. Its stage cap is reduced to 1,500 seconds (25 minutes); this does not authorize increasing per-fit limits. Its output is `results/step1-20261020/smoke-retry/`. The original run is not relabeled successful or merged into the retry. There will be no automatic statistical retry to remove numerical failures.

```powershell
uv run python benchmarks/run.py --stage smoke --config benchmarks/validation.toml --budget-seconds 1500 --output results/step1-20261020/smoke-retry
```

## Recorded outcome (after execution)

Software checks: 51 tests passed, lint clean, package build successful. The retry completed in 830.57 seconds with 33 successes, one inconclusive reference, five method timeouts, and twelve untested applications (39/51 attempted). All four production Gibbs/KDE references passed; 14/15 total references passed. Every method succeeded on the Gaussian fixture. Five KDE samplers timed out on the longer AR fixture, and the final complete method block could not be reserved within the remaining budget. The smoke status is incomplete; the research gate rejects it.

See [VERIFICATION.md](VERIFICATION.md) for interpretation and [the retry report](../../results/step1-20261020/smoke-retry/report.md) for the machine-recorded outcomes. Earlier failed/interrupted evidence remains unchanged. No statistical retry or four-hour research campaign immediately followed this incomplete stage. The subsequent [declared follow-up](FOLLOWUP_VALIDATION.md) changes the evaluated implementation, preserves these results, and records the later validated smoke stage.
