# Research conclusions — 21 October 2026

For delivery and test outcomes across all four epics, see the [executive summary](EXECUTIVE_SUMMARY.md).

The prototype is implemented and its numerical/reporting repairs pass the complete software checks. **A general predictive advantage of bidirectional KDE over pooled KDE has not been established.** The available comparison is exploratory, incomplete and subject to the execution-provenance limitations below.

## What was retained

The research process exited on a Windows progress-file replacement error after **792 method applications across 66 primary series/gap cases**. Its last telemetry was 230.17 minutes; this is not an independently measured total exit runtime. Of those applications, **691 succeeded and 101 timed out**. All successful saved prediction files passed the independent observed-data/hash, gap/endpoint, RMSE/MAE and coverage-count audit.

The original files remain untouched. Separate [recovered accounting](../../results/followup-20261021/research-recovered/recovery.json) preserves the raw journal prefix and records all **5,160 planned application identities**, including **4,368 untested applications**. Recovery added no predictions and resumed no inference. The [integrity audit](../../results/followup-20261021/research-recovered/integrity-audit.json) reconciles raw hashes, the previous report, journal prefixes, recovered results and the terminal manifest. Thus the measurements were retained; the intended research campaign was not completed cleanly.

## Reliability is the clearest finding

| Recorded method | Successful / attempted | Timeouts |
|---|---:|---:|
| BiLA KDE | 44 / 66 | 22 |
| Pooled KDE | 44 / 66 | 22 |
| Fixed-weight KDE | 44 / 66 | 22 |
| Left-only KDE | 48 / 66 | 18 |
| Right-only KDE | 49 / 66 | 17 |
| Gaussian bridge | 66 / 66 | 0 |
| Bayesian local-level smoother | 66 / 66 | 0 |
| Bayesian level-AR smoother | 66 / 66 | 0 |
| Fixed-parameter AR counterpart | 66 / 66 | 0 |

Endpoint-corrected KDE, linear interpolation and PCHIP also returned outputs on all 66 attempted cases. These counts measure successful completion of their defined contracts, not equal predictive quality or equal uncertainty guarantees across deterministic and probabilistic methods.

BiLA and pooled KDE succeeded on every attempted gap of 10 or 30 missing values and timed out on **every one of the 22 attempted gaps of 100 values**, under the declared 60-second/2-GiB per-application limits and precision requirements. There are no jointly successful BiLA/pooled pairs at gap 100. This is a practical limit of obtaining the required ensembles with this implementation and budget; it does not establish that the conditional model cannot reconstruct longer gaps with other computation settings.

Runtime describes an interactive laptop: dashboard work and short browser checks occurred during the research run. No heavy scientific/performance suite ran concurrently. The observation does not identify which activity caused any particular timeout.

## Predictive comparison remains inconclusive

Gaussian and skewed settings reached six independent series per gap size; changing-scale and changing-shape settings reached five. The target was thirty. Prior-sensitivity and AR/GARCH stress partitions were not reached. See the exact [replication table](../../results/followup-20261021/research-recovered/replication.csv).

The primary six-cell adaptation contrast includes changing scale and shape at gaps 10, 30 and 100. It is **unavailable**, because its longer-gap cells have no successful pairs. Removing those cells and declaring an overall adaptation win would change the predeclared question.

For the shorter gaps, the following exploratory results use matched, jointly successful series. Negative BiLA-minus-pooled energy favors BiLA; positive favors pooled. Scores are compared within settings.

| Scenario | Gap | Pairs | Mean energy difference | Exploratory 95% bootstrap interval |
|---|---:|---:|---:|---|
| Gaussian | 10 | 6 | +0.0710 | [+0.0397, +0.1087] |
| Gaussian | 30 | 6 | −0.0453 | [−0.1170, +0.0045] |
| Skewed | 10 | 6 | +0.0448 | [−0.0098, +0.1036] |
| Skewed | 30 | 6 | +0.0311 | [−0.0753, +0.1423] |
| Changing scale | 10 | 5 | −0.0391 | [−0.1334, +0.0176] |
| Changing scale | 30 | 5 | −0.0087 | [−0.1865, +0.0954] |
| Changing shape | 10 | 5 | −0.0642 | [−0.1209, −0.0104] |
| Changing shape | 30 | 5 | +0.0332 | [−0.0731, +0.1930] |

The directions are mixed. The changing-shape, short-gap result is a lead for further investigation, while the Gaussian short-gap result favors pooled KDE. Five/six series, multiple comparisons and predictive Monte Carlo error prevent treating either selected cell as a confirmatory conclusion. The bootstrap resamples series, has no multiplicity adjustment and omits additional predictive Monte Carlo uncertainty; the [complete analysis](../../results/followup-20261021/research-recovered/analysis.md) reports coarse score MCSE separately.

The analysis also retains matched comparisons with the Gaussian and Bayesian competitors. Their higher recorded completion rates matter alongside path scores. This evidence does not establish that BiLA outperforms Bayesian imputation, and cannot separate every model/parameter-uncertainty effect without the unreached sensitivity study.

## What the checks do and do not establish

- Software correctness: **125 tests passed**, one Windows symlink-permission fixture skipped; lint and sdist/wheel build passed. The full suite includes density equivalence, extreme floating-point scales, exact returned endpoints, typed failures, resource enforcement and the longer-gap performance headroom contract.
- Sampler/reference accuracy: the earlier source passed 51/51 smoke applications. The corrected source's fresh [smoke stage](../../results/followup-20261021/smoke-repaired/report.md) passed **51/51 applications in 657.07 seconds**: all 15 references and 36 method applications. Its [terminal audit](../../results/followup-20261021/smoke-repaired/artifact-audit.json) verifies all prediction artifacts, planned identities and live/archived source/configuration hashes. Peak recorded process memory was 288.21 MiB, with the original precision/resource requirements and no fallback.
- Empirical calibration: coverage and widths are reported on successful outputs. Failed reconstructions are retained. Successful-case coverage alone does not establish overall calibration, especially when long-gap fits fail.
- Uncertainty scope: KDE ensembles condition on fitted densities and bandwidths; they do not propagate density-estimation uncertainty. Full Bayesian competitors integrate parameter uncertainty, with fixed-parameter counterparts available as controls.
- Artifact limits: raw chains were not retained under the declared configuration. Energy/CRPS and empirical interval bounds cannot be independently reconstructed from saved point summaries; their recorded values are not claimed to have been independently recomputed.

## Execution provenance

The campaign started with source signature `ca1cdbbb0259b8b1a17c84f9eae2f7c8c0e4d4e6bc114392b13ed679a2a9df23`, preserved in [the initial snapshot](../../results/followup-20261021/source-executed/snapshot.json). Post-interruption inspection found only one difference from those execution/configuration bytes: `normal = lambda: ...` became an equivalent local `def normal(): ...` in `sampling.py`. Its operation sequence is unchanged, but the rewrite occurred during the run. The observed later signature was `f477d624187236d415dad5ac419dbe0ae504bd474317e42825b31e8f4ac6cf19`. Neither the author nor each worker's loaded source hash was recorded. The source-freeze criterion was therefore not met; this is not represented as a clean single-version experiment.

After termination, the extreme-scale density repair and bounded publication retry were integrated and independently reviewed. A real Windows reader-lock probe reproduced the original replacement failure, and a release-after-50-ms probe succeeded with the repair. The original failure's particular reader was not identified. Persistent replacement failures still raise and preserve old/temporary evidence.

The corrected source has signature `c57a22862ea9eb6d488f8fad0c5c49a8363e0a1da3e4419fd04bf5aef419c8d8`, archived separately in [source-repaired](../../results/followup-20261021/source-repaired/snapshot.json). Its software checks and fresh smoke evidence must remain distinct from the interrupted campaign. No scientific threshold, requested quantile, resource ceiling or model scope was relaxed to obtain a pass.

## Recommended next investigation

The next scientific task should target **the cost of reaching the required Monte Carlo precision for 100-point KDE bridges**. Profile a small fixed set of cases, distinguish density-evaluation cost from chain mixing, and evaluate improvements that preserve the fitted target and current quality requirements. This should precede a larger comparative campaign or added dependence modeling.

Before any future campaign, run from an immutable source snapshot, record per-worker provenance and retain robust publication/error finalization. A dedicated workstation interval would improve runtime interpretability. Then a separately authorized study can seek adequate paired replication, calibration and the missing sensitivity/stress evidence. No additional four-hour campaign, model extension or real-data study is authorized or executed by this follow-up.

Mathematical foundations and prior work are maintained in [REFERENCES.md](REFERENCES.md); full software and validation history is in [VERIFICATION.md](../validation/VERIFICATION.md).
