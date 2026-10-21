# BiLA-KDE Bridge

Read the [executive summary by epic](../research/EXECUTIVE_SUMMARY.md) for what was delivered, tested and concluded, including the incomplete research results and recommended next step.

Probabilistic interpolation of one internal gap in a regularly sampled univariate series. Gaussian KDEs fitted to observed forward increments on both sides are blended linearly across the gap, then conditioned on the observed endpoint displacement using elliptical slice sampling with conditional Gaussian-kernel Gibbs updates.

The initial model assumes independent increments **before** conditioning. The endpoint constraint introduces dependence in the bridge. Uncertainty is conditional on the fitted KDEs; density-estimation uncertainty and explicit serial dependence are outside this version.

Mathematical foundations, prior work, and primary software references are maintained in [REFERENCES.md](../research/REFERENCES.md). The predeclared updated-sampler validation protocol is in [STEP1_VALIDATION.md](../validation/STEP1_VALIDATION.md).

The tail-precision investigation, numerical repairs and validation sequence are recorded in [FOLLOWUP_VALIDATION.md](../validation/FOLLOWUP_VALIDATION.md). Resource limits and scientific thresholds are unchanged. The research campaign was interrupted during Windows progress publication; its separately [recovered evidence](../../results/followup-20261021/research-recovered/analysis.md) preserves 691 successes, 101 timeouts and all unreached applications. The corrected source passes 125 tests and its fresh 51/51 smoke stage. Comparative superiority is not established; see [research conclusions and next steps](../research/RESEARCH_CONCLUSIONS.md).

## Local work dashboard

```powershell
uv run python -m scripts.issue_dashboard --open
```

Open [the local dashboard](http://127.0.0.1:8765) to monitor scratch issues and epics, completed implementation history, dependencies and recorded research progress. Select Results & conclusions on any epic card to open its research briefing in a centered window over a blurred dashboard. Choose Board, List or Dependency; the dependency graph shows prerequisite arrows and opens task details. A collapsible campaign thread explains recorded actions, results and next steps. It refreshes from local sources every ten seconds. The tracker and live history are local workspace state and are excluded from the public checkout. See [the tracker index](../../.scratch/README.md) and [dashboard usage and checks](../../.scratch/issue-dashboard/README.md).

## Setup and example

Requires Python 3.13 or newer.

```powershell
uv sync
uv run python examples/quickstart.py
uv run pytest
```

The example also runs with `uv run python main.py`. Scripts that call inference must use a `if __name__ == "__main__":` guard because each fit uses a supervised worker process.

For visual before/after examples with Gaussian increments, skewed increments, and changing drift and volatility:

```powershell
uv run --group examples python examples/plot_gaps.py --samples 24000 --fallback-90
```

Open [the generated gallery](../../results/examples/before_after.png). Each row shows the input with a gap, the imputed series, and a gap close-up with sampled paths and synthetic hidden truth. Pointwise 95% bands appear only when their precision checks pass. The curated final output directory also contains the styled GIF and diagnostic records. These are illustrations, not evidence of predictive calibration or superiority.

One of the 24 displayed paths (the first retained draw) is highlighted in opaque purple. To replot saved samples, use `uv run --group examples python examples/plot_gaps.py --reuse`.

Use `--samples 24000` to request a larger ensemble under the same per-fit resource limits. More samples may resolve interval-precision failures; any remaining failures are retained in the diagnostics and the affected bands stay hidden.

The optional `--fallback-90` checks a 90% interval only if the 95% interval fails precision. The plot labels each displayed coverage explicitly, and diagnostics retain the failed 95% check. The current larger gallery shows 95% bands for the first two examples and a 90% band for the third; every displayed band passed the same MCSE/std threshold. These coverage levels describe fitted-model probability, not an empirically established coverage rate.

After generating the examples, plot their distribution evolution:

```powershell
uv run --group examples python examples/plot_distributions.py
uv run --group examples python examples/animate_distributions.py
```

[Distribution evolution](../../results/examples/distribution_evolution_styled.gif) animates the fitted increment mixture and endpoint-conditioned bridge for the changing-dynamics example, with its stated pointwise band and one fully opaque sampled path.

Only the latest [styled GIF](../../results/examples/distribution_evolution_styled.gif) is retained in the final example folder. Intermediate NPZ files and the older three-example GIF have been removed; rerun sample generation before regenerating visualizations.

For a compact, polished animation focused on the changing-dynamics example, run `uv run --group examples python examples/animate_styled.py`. The [styled GIF](../../results/examples/distribution_evolution_styled.gif) pairs the evolving increment density with the reconstructed bridge, its labeled 90% pointwise band, and one opaque purple path. A smooth cursor follows that path over an approximately five-second loop; intermediate positions interpolate the displayed lines for animation and do not introduce additional observations. The generator can also export a PNG poster; only the current GIF and before/after gallery are retained in the curated example folder.

Each sampler iteration retains the density-corrected elliptical slice move and adds four blocked Gibbs sweeps. A Gibbs sweep samples Gaussian KDE kernel labels conditional on the current increments, then samples a Gaussian bridge conditional on those labels and the endpoints. Both moves preserve the fitted KDE bridge target. This improves exploration of skewed, changing densities; it does not guarantee that every gap meets the unchanged diagnostic thresholds within its budget.

```python
from bilakde import BiLAKDEBridge, BridgeError

if __name__ == "__main__":
    # series: numeric array/list, or pandas Series with regular DatetimeIndex.
    # Exactly one internal NaN block; default windows need 101 observed levels
    # on each side, including the observed endpoint.
    try:
        result = BiLAKDEBridge(random_state=42).fit_transform(series, n_samples=4000)
        completed = result.imputed_series
        paths = result.samples  # (4000, missing_count + 2), fixed endpoints included
        bands = result.quantiles([0.025, 0.5, 0.975])
    except BridgeError as exc:
        print(exc.status, exc.reason, exc.diagnostics)
```

The completed series uses the ensemble mean inside the gap and preserves observed values and pandas index/name/timezone metadata. Samples are correlated MCMC output with their four-chain ordering retained. Inspect `result.diagnostics`; a successful diagnostic screen is not a proof of convergence or predictive calibration.

Default runtime/memory limits are 60 seconds and 2 GiB per fit. Configure them with `SamplingConfig`. All expected unsuccessful calls raise typed exceptions with evidence, never a partial reconstruction. Quantile precision can independently raise `SummaryPrecisionError` even when the path ensemble is valid.

## Input and modeling limits

- NumPy-compatible real numeric vectors use a regular unit grid.
- pandas Series require strictly increasing, unique, equally spaced actual elapsed timestamps. UTC-hourly data may span a DST change; local daily data with 23/25-hour intervals is irregular and rejected.
- Explicit window counts are exact and at least 20 increments per fitted side. The default is 100; unavailable windows are not silently shrunk or expanded.
- Gaussian KDE uses the univariate Scott rule separately per fit. Constant/nearly constant increment samples fail explicitly rather than gaining artificial noise.
- Multiple gaps, boundary gaps, nonfinite observations, irregular timing, lossy numeric conversion, learned weights, and detrending are unsupported.

## Reproducible research stages

```powershell
uv run python benchmarks/run.py --stage smoke --config benchmarks/validation.toml --output results/smoke
uv run python benchmarks/run.py --stage research --config benchmarks/validation.toml --smoke results/smoke --output results/research
```

Smoke testing is capped at 30 minutes; research is capped separately at four hours. Research requires validated smoke evidence for the exact current source and configuration. Existing output directories are never overwritten. `--budget-seconds` may lower a cap for runner checks.

The current validation configuration requests 24,000 predictive paths per stochastic competitor and 32,000 per reference check, with JSON prediction summaries and no saved NPZ chains. The original smaller configuration remains in `benchmarks/default.toml`. See [the fixed validation plan](../validation/STEP1_VALIDATION.md) for accuracy criteria and the recorded infrastructure interruption.

The declared lineup includes pooled/fixed/one-sided KDE controls, endpoint-corrected KDE, Bayesian local-level and level-AR(1), their fixed-parameter counterparts, linear interpolation, and PCHIP. Full Bayesian competitors integrate parameters; the proposed KDE model remains a plug-in density estimator. The Bayesian AR implementation uses marginalized gap transitions and checked one-dimensional posterior quadrature, followed by conditional Gaussian path draws.

The primary outcome is path energy score; CRPS, variogram scores, coverage/width, point errors, reliability, and computation costs are secondary. Thirty independent series per primary setting is an exploratory target, not a power guarantee. Balanced paired cases, unsuccessful methods, and cases not reached before the cap remain visible.

Each run writes source/configuration hashes, exact run order, `progress.json`, append-only case records, prediction artifacts, full results, and a Markdown report with paired exploratory intervals. Prediction artifacts use JSON when `save_chains=false`; retained-chain NPZ output is optional when `save_chains=true`. Results are local under the ignored `results/` directory. Numerical verification and actual campaign outcomes must be read from those artifacts; planning or a passing unit suite does not establish scientific superiority.

For a finished research run using JSON artifacts, `uv run python -m scripts.research_summary results/research` adds an artifact audit and descriptive analysis of achieved replication, failures, matched primary comparisons, and the predeclared adaptation contrast. The reporter refuses an ongoing run and preserves prior-sensitivity variants. Its bootstrap intervals are exploratory; successful-case calibration and accuracy must be read with failure rates and missing target counts.

## Packaging

`uv build` produces the installable `bilakde` import package. Runtime dependencies and development tools are locked in `uv.lock`. The research tooling lives in the repository's `benchmarks/` directory and is run from a checkout.
