# Implementation verification — updated 2026-10-21

The library and declared benchmark tooling are implemented. The corrected source passes **125 tests / one Windows fixture skip**, lint and package build. Its fresh source-specific [smoke stage](../../results/followup-20261021/smoke-repaired/report.md) is **validated: 51/51 successes in 657.07 seconds (10.95 minutes)**. All 15 references and 36 method applications passed, and all successful artifacts were independently reconciled. The 24 live/archived execution and configuration files match the final snapshot; peak recorded process memory was 288.21 MiB. No thresholds, quantiles or per-application limits were relaxed. See [the terminal smoke audit](../../results/followup-20261021/smoke-repaired/artifact-audit.json) and [research conclusions](../research/RESEARCH_CONCLUSIONS.md). Mathematical foundations and primary sources are maintained in [REFERENCES.md](../research/REFERENCES.md).

The earlier source passed 51/51 follow-up smoke applications. Its research campaign then exited with a Windows progress-file replacement error after 792 attempts: **691 successes, 101 timeouts**. A [separate recovered audit](../../results/followup-20261021/research-recovered/analysis.md) reconciles all 5,160 planned statuses, including 4,368 untested applications, without resumed inference. Five or six series per primary setting were reached; no successful BiLA/pooled pairs exist at gap 100, so the declared adaptation contrast is unavailable. A lambda-to-equivalent-function rewrite occurred during execution; initial and observed source hashes are preserved, but one unchanged per-worker source version cannot be claimed. Details are in [FOLLOWUP_VALIDATION.md](FOLLOWUP_VALIDATION.md). This is exploratory interrupted evidence, not a clean completed research campaign or proof of superiority.

## Software checks

The local [work dashboard](http://127.0.0.1:8765) now monitors four scratch epics, including six completed implementation milestones. Its separate checks record 38 Python tests, seven Node tests and twelve Chromium scenarios passing, with one unavailable Windows symlink fixture skipped. The campaign thread refreshes timestamped explanations and preserves expansion and reading position. The third Dependency view retains recursive prerequisite context, accessible details, zoom and refresh state; a reviewed regression checks that skipped-column links avoid intermediate cards. Independent reviews and regression fixes are recorded in the [dashboard ledger](../../.scratch/issue-dashboard/ledger.md); latest rendered evidence is in [evidence/dependency](../../.scratch/issue-dashboard/evidence/dependency). This monitoring evidence does not change the scientific campaign's status or source version.

- Current complete suite: **125 passed / one Windows fixture skipped in 99.18 seconds** (`uv run pytest -q`), including twelve extreme-density regressions, bounded publication failures and the longer-gap performance contract. The preceding optimization suite had 63 tests; the original implementation suite had 47.
- Lint: clean (`uv run ruff check src tests benchmarks scripts examples main.py`).
- Packaging: source archive and wheel built with `uv build`.
- Array/pandas inference, exact returned-block diagnostics, quantiles, typed failures, deadline/memory enforcement, and Windows descendant cleanup have tests.
- Independent review found three significant defects in the initial implementation. Regression tests reproduced and verified fixes for returned-level rounding, incomplete oracle precision evidence, and missing chain uncertainty in energy-score precision.
- Bayesian checks cover the gap likelihood, conjugate local-level posterior, posterior quadrature, and hand-derived correlated AR bridge moments. These are numerical implementation checks, not proof of universal inferential correctness.

## Earlier validated follow-up — initial source, 21 October

[Declared follow-up](FOLLOWUP_VALIDATION.md) · [Validated smoke report](../../results/followup-20261021/smoke/report.md) · [Full results](../../results/followup-20261021/smoke/results.json) · [Manifest](../../results/followup-20261021/smoke/manifest.json)

The original tail issue reproduced under all three declared seeds (2026–2028) using the original elliptical-only transition; independent exact-mixture draws passed the same tail screen. The complete current production transition (ellipse plus four conditional-kernel Gibbs sweeps) subsequently passed all three seeds against the unchanged frozen law. The elliptical-only ablation remains reproducible using `benchmarks.diagnose_tail --elliptical-only`; earlier inconclusive evidence remains preserved.

Profiling found repeated log-sum-exp work was the main runtime cost. A cached finite-Gaussian-mixture engine now evaluates the same densities with stable exponential sums, reuses fixed coefficients, and collapses duplicate KDE components in the relevant controls. No bandwidth, endpoint constraint, target law, numerical acceptance threshold, or per-fit resource limit was relaxed. A rare zero-uniform/zero-probability component selection edge case was also reproduced and corrected.

The fixed 8,000-path AR-fixture profile dropped from 37.08 to 12.44 seconds. A direct archived 24,000-path evaluation took 50.40 seconds, failing the stricter software headroom regression (<40 seconds) although it could complete under 60 seconds on the idle machine. The optimized implementation passes that regression and the full 63-test suite. All five KDE ablations are checked against independent frozen density formulas with unequal observed windows.

The fresh scientific smoke stage completed **51/51 applications successfully in 589.36 seconds (9.82 minutes)** under its original 30-minute cap. All 15 references passed, including whole-path and tail checks, and all twelve methods passed all three fixtures. No application timed out, failed precision, or remained untested. All requested quantiles were retained, with no illustrative 90% fallback. That smoke source signature matches its manifest, and the research gate accepted these results for the exact validation configuration. JSON summaries are used; no NPZ files were added.

Smoke checks support bounded-case numerical correctness and feasibility. They do not establish population calibration, comparative superiority, or universal mixing. The separately budgeted research run is recorded at `results/followup-20261021/research/`; its status and actual achieved replication counts must be read from its manifest and results. No research outcome is claimed while it is running.

## Earlier Step 1 validation — 20 October (historical)

[Predeclared plan](STEP1_VALIDATION.md) · [Current smoke report](../../results/step1-20261020/smoke-retry/report.md) · [Full results](../../results/step1-20261020/smoke-retry/results.json) · [Manifest](../../results/step1-20261020/smoke-retry/manifest.json)

The bibliography now contains 22 annotated references. Validation adds exact enumeration of time-varying fitted Gaussian-KDE bridges that exercise the production conditional-kernel Gibbs updates. Reference checks now include whole-path squared-norm expectations and 2.5%/97.5% marginal quantiles at the first, middle and last missing coordinates, alongside the existing means, covariance, CDF and chain checks. The fixed validation configuration requests 32,000 reference samples and 24,000 predictive paths per stochastic method, retaining 60-second/2-GiB per-fit limits and all existing acceptance thresholds. Scientific evaluation does not use the illustrative 90% fallback.

The first attempt was interrupted by an unexplained elapsed-clock jump consistent with suspension: the ninth case recorded 10,811.55 seconds against a 60-second deadline. Its unchanged evidence remains in `results/step1-20261020/smoke/`; its wall-time overrun must not be represented as a completed bounded CPU run. A single documented infrastructure retry used identical source/configuration/seeds and a reduced 25-minute cap.

The retry finished in **830.57 seconds (13.84 minutes)**. It attempted **39/51 runs (76.5%)**; **33 succeeded**, **one reference was inconclusive**, **five method applications hit their time limit**, and **12 were untested**. Peak recorded working set was **289.29 MiB**. Source signatures match the current benchmark/library code. No NPZ files were written: successful prediction summaries are JSON, and raw chains are not retained under this configuration.

| Check | Result |
| --- | --- |
| Production Gibbs/KDE exact-reference cases | **4/4 passed**, for four/six increments and typical/displaced endpoints. Frozen and production log densities agreed within 7.11e-15 at the declared probes. |
| All reference cases | **14/15 passed**. The displaced four-increment two-component mixture, using the original elliptical-only transition, remains inconclusive on tail quantiles. |
| Gaussian fixture, ten missing values | **12/12 methods succeeded**, including every required quantile and probabilistic score for stochastic methods. |
| AR Gaussian stress fixture, thirty missing values | **7/12 methods succeeded**. BiLA, pooled, fixed-weight, left-only and right-only KDE reached their 60-second limits. |
| Changing-shape fixture, thirty missing values | **12 methods untested**. The remaining 669.43 seconds were below the unchanged reservation rule of 12 × 60 + 5 = 725 seconds for a complete method block. |

The inconclusive reference passed chain diagnostics and the mean, covariance, midpoint-CDF and path-quadratic checks. Its maximum standardized tail-quantile discrepancy was 0.13233 and maximum tail-quantile MCSE was 0.06884; the two-SE tail-accuracy screen was not established. These maxima need not occur at the same coordinate. The result does not establish bias, but it prevents declaring the reference validation complete.

All twelve methods now have at least one complete successful result, an improvement over the original smoke stage. The reference requirement still fails, so the smoke manifest is **incomplete**. The research gate was explicitly checked: it rejects this evidence before creating a research output directory. No statistical retry was performed to remove the inconclusive result or the resource failures.

Step 1 establishes useful bounded-case evidence for the refined sampler, not general tail accuracy, calibration, or comparative superiority. The next work is a targeted investigation of the inconclusive tail reference and the cost of obtaining precise ensembles for longer gaps within the fixed resource budget, followed by a new declared validation run. Adding model features or starting the research campaign is premature.

## Original smoke evidence (historical)

[Full report](../../results/smoke-20261020-implementation/report.md) · [Case-level results](../../results/smoke-20261020-implementation/results.json) · [Source/configuration manifest](../../results/smoke-20261020-implementation/manifest.json)

The single declared smoke stage attempted **47/47 runs in 455.04 seconds (7.58 minutes)**. Peak recorded worker working set was **226.38 MiB**. No thresholds or resource caps were relaxed and no statistical rerun occurred.

| Outcome | Runs |
| --- | ---: |
| Success | 19 |
| Oracle diagnostic/inconclusive | 1 |
| Requested-quantile precision unmet | 23 |
| Retained-draw cap | 2 |
| Time cap | 2 |

Ten of eleven reference checks passed. The six-increment mixture at a typical endpoint was inconclusive under the two-SE covariance-precision screen: covariance discrepancy 0.0525 plus twice estimated Monte Carlo error 0.0524 exceeds the 0.15 tolerance. Its chain checks passed. This is insufficient validation precision, not evidence that its target law is wrong.

No BiLA-KDE smoke case met the complete inference-plus-interval output contract: two failed the requested quantile precision check and one exhausted its retained-draw cap. Other KDE controls also had precision/resource failures. The report retains all failures; its successful-case scores cannot be read as an overall ranking.

The research command was explicitly checked to refuse this incomplete smoke evidence before creating a research output directory. The four-hour campaign remains unrun.

## Version and reproduction limits

After the original smoke completion, a regression test exposed NumPy configuration scalars that were not JSON-serializable. The configuration now normalizes valid scalar values to native Python numbers. That metadata-only revision passed the then-current 47-test suite and wheel build without changing the sampling/scoring algorithms. The original smoke manifest preserves its executed source hash; it was not rewritten to match that revision. No validated smoke artifact existed for that intermediate revision; the later validated 21 October version is described above.

The sampler was subsequently refined while debugging the fixed changing-drift/volatility visual example. The former global elliptical-slice transition alone exhausted its 10,000-update cap: R-hat 1.0542, minimum bulk/tail ESS 53.46/39.25. A reduced 2,000-update regression reproduced the failure. Each KDE sampling iteration now combines the original corrected elliptical-slice move with four blocked Gaussian-kernel Gibbs sweeps. Kernel labels are sampled conditional on the current increments, then a Gaussian bridge is drawn conditional on the labels and endpoint sum. Both transitions preserve the same fitted KDE bridge law; this is not unconditional KDE sampling followed by an arbitrary endpoint correction.

New verification covers preservation of an exactly enumerated two-increment KDE bridge distribution (moments and CDF values), and successful reconstruction of the unchanged third example at the original seed, data, 8,000 requested samples and diagnostic thresholds, with a tighter 2,000-update cap. Requested tail-quantile precision remains an independent check. Earlier example artifacts are retained in `results/examples-before-sampler-fix/`. This algorithm change supersedes the earlier metadata-only revision and requires new scientific smoke validation; the original smoke results above remain historical evidence for the old sampler.

The original public example script was rerun with the default 60-second/2-GiB/10,000-update limits and original seeds. All three path ensembles passed. The third completed in 19.74 seconds with R-hat 1.00481, bulk ESS 1400.03 and tail ESS 1377.76. Its requested 95% quantiles still failed the separate precision screen (maximum MCSE/std 0.20364 versus the 0.10 threshold), so no band is shown. The skewed example also withholds its band. Static galleries and the animated density-evolution GIF are generated from the new accepted ensembles; these illustrations are not a new scientific smoke campaign. The refined source archive and wheel were rebuilt successfully.

A later illustration run requested 24,000 paths per example, preserving the same data, seeds, per-fit resource limits and precision threshold. All three ensembles passed; the first two also passed the 95% interval check. The third still failed that check (maximum MCSE/std 0.13759), but passed a separately requested 90% interval check. The current gallery explicitly labels its third band as 90%, retaining the failed 95% status in diagnostics. The animated GIF shades these accepted intervals at each time step and runs at three frames per second. The 8,000-path artifacts remain in `results/examples-8000-paths/`, and the 24,000-path run before the optional 90% fallback remains in `results/examples-24000-paths/`. The current files in `results/examples/` use the 24,000-path ensembles and accepted labeled bands. None of these illustrations changes the scientific smoke protocol or establishes predictive calibration.

Use `uv sync`, `uv run pytest`, and `uv run python examples/quickstart.py` for software verification. Benchmark defaults and the gated stage commands are described in [README.md](../../README.md).

The tail-reference precision and runtime limitations identified by the earlier Step 1 run were addressed in the declared 21 October follow-up for the tested smoke fixtures. The earlier plans and results preserve the executed settings and unsuccessful records. Current research conclusions must come from the separately capped campaign; smoke validation alone is not scientific superiority or calibration evidence.

This verification record predates initial public publication. The repository README describes the published checkout; source-specific numerical evidence above remains a historical record.
