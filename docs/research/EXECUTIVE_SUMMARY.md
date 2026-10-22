# Executive summary — 21 October 2026

This is a historical snapshot: epic counts, checks and recommended next steps below describe 21 October. For later dashboard deliveries and the planned native-kernel investigation, see the [change history](../releases/CHANGELOG.md) and [next-investigation note](native-kernels-and-path-budgets.md).

**The research prototype and local dashboard are delivered. The corrected software passes its checks. BiLA-KDE's predictive superiority is still unproven.** The comparative campaign was interrupted; its measurements were recovered without restarting inference.

All **4 epics and 29 issues are resolved (100% of the tracked work)**. This measures closure with recorded outcomes, including unsuccessful outcomes. It does not mean that the planned scientific study completed or that its hypothesis was confirmed.

## At a glance

| Epic | Work closed | What was delivered | Main result / conclusion |
|---|---:|---|---|
| [Research prototype specification](../../.scratch/bila-kde-prototype/map.md) | 10/10 issues | Mathematical target, model scope, API and validation protocol; independent/dependent feasibility comparison | Independent increments selected for the first version; explicit dependence deferred. Feasibility supported this practical choice, not predictive superiority. |
| [Prototype implementation](../../.scratch/bila-kde-implementation/map.md) | 6/6 issues | Python package, guarded conditional sampler, probabilistic competitors, scoring, examples and packaging | Usable research prototype for one internal gap, with exact endpoint constraints and explicit failures. Long-gap precision within the default budget remains a limitation. |
| [Validation and research conclusions](../../.scratch/bila-kde-validation/map.md) | 7/7 issues | Numerical/reporting repairs, fresh validation, recovered campaign audit and qualified conclusions | Corrected-source smoke: **51/51 passed**. Comparative research: **691 successes, 101 timeouts, 4,368 untested**. No overall BiLA advantage established. |
| [Live issue dashboard](../../.scratch/issue-dashboard/map.md) | 6/6 issues | Epic cards, Board/List/Dependency views, completed history, filters and collapsible campaign explanations | Local monitoring delivered and verified. Recorded campaign activity is distinguished from current process health. |

## 1. Research prototype specification

**Done.** Turned the proposal into a precise, implementable experiment: regularly sampled univariate input, one internal gap with observed endpoints, two local Gaussian KDEs, deterministic bandwidths and linear blending. The initial increments are independent before conditioning; the endpoint constraint then couples them. Ensembles represent uncertainty conditional on the fitted densities, without integrating density-estimation uncertainty.

**Tested.** A disposable CPU feasibility run attempted **79/79 cases in 9.35 minutes**, with a measured 185 MiB peak working set. All **7 reference screens passed**. Among fitted KDE screens:

| Missing values | Independent increments: passed / attempted | Previous-increment-dependent model: passed / attempted |
|---:|---:|---:|
| 10 | 12/12 | 12/12 |
| 30 | 12/12 | 11/12 |
| 100 | 11/12 | 0/12 |

The remaining cases were inconclusive within their budgets, not demonstrated mathematical failures.

**Conclusion.** Start with the simpler independent-increment model. This screen compared computational feasibility of two different conditional models; it did not compare BiLA against pooled KDE or establish predictive calibration. Its disposable settings differ from the later, stricter research protocol.

Evidence: [agreed specification](../../.scratch/bila-kde-prototype/spec.md), [feasibility results and limitations](../../.scratch/bila-kde-prototype/evidence/summary.md).

## 2. Prototype implementation

**Done.** Implemented NumPy and checked regular-datetime pandas inputs, observed-only fitting windows, endpoint-conditioned sampling, ensemble-mean completion, sampled paths, precision-checked quantiles and typed diagnostic exceptions. The sampler combines density-corrected elliptical slice moves with conditional Gaussian-kernel Gibbs updates. Defaults remain **60 seconds and 2 GiB per fit**. Added twelve benchmark methods, including Bayesian local-level and level-AR smoothers and fixed-parameter controls.

**Tested.** Checks cover input rejection and metadata, KDE and Gaussian-conditioning laws, endpoint preservation, sampler/reference behavior, summary precision, failures, supervised resource enforcement, Bayesian/scoring machinery and packaging. The latest combined repository suite, including follow-up repairs and dashboard tests, is **125 passed / 1 skipped**; lint and wheel/source builds passed. The skip concerns a Windows symlink-permission fixture. These are current combined checks, not 125 tests attributable solely to this historical implementation epic.

**Conclusion.** The prototype is suitable for controlled research within its documented scope. A returned ensemble must pass diagnostics, and a requested band can fail its additional precision check. Successful software tests do not establish convergence for every future input or predictive superiority.

Visual outputs: [before/after examples](../../results/examples/before_after.png), [animated distribution evolution](../../results/examples/distribution_evolution_styled.gif), [example diagnostics and interpretation](../../results/examples/README.md). The third illustration uses a labeled, checked 90% band after its 95% check failed; this fallback was not used in scientific evaluation.

Evidence: [verification record](../validation/VERIFICATION.md), [public usage and limits](../../README.md).

## 3. Validation and research conclusions

**Done.** Investigated tail precision and runtime, repaired extreme-scale density calculations, reproduced Windows progress-publication contention and added bounded retries. Preserved the interrupted campaign's raw files, reconstructed terminal accounting separately and audited successful prediction artifacts. No inference was resumed during recovery.

**Tested.** The corrected source passed a fresh **51/51 smoke stage in 10.95 minutes**: 15 reference cases and 36 method applications. All 36 saved prediction artifacts were reconciled against their data, gaps, endpoints and independently computable metrics; peak recorded process memory was **288.21 MiB**. Source/configuration hashes matched the archived corrected snapshot. Resource limits, requested intervals and acceptance thresholds were unchanged.

**Research results.** The original campaign attempted **792/5,160 planned applications (15.3%)** across 66 series/gap cases. Of the attempted applications, **691 succeeded (87.2%)** and **101 timed out (12.8%)**; **4,368 applications (84.7% of the plan) were untested**. These percentages describe different denominators and are not measures of predictive accuracy.

| Competitor | Successful / attempted | Practical finding |
|---|---:|---|
| BiLA KDE | 44/66 | All attempted gaps of 10/30 passed; all 22 gaps of 100 timed out. |
| Pooled KDE | 44/66 | Same completion pattern as BiLA. |
| Gaussian bridge | 66/66 | Completed every attempted case under its contract. |
| Bayesian local-level smoother | 66/66 | Completed every attempted case under its contract. |
| Bayesian level-AR smoother | 66/66 | Completed every attempted case under its contract. |

**Conclusion.** Short-gap energy-score differences are mixed. Changing-shape gaps of 10 give an exploratory lead for BiLA; Gaussian gaps of 10 favor pooled KDE. Only five or six independent series per setting were reached, against a target of thirty. No jointly successful BiLA/pooled pairs exist at gap 100, so the predeclared overall adaptation comparison is unavailable. Higher completion rates do not by themselves establish better predictive accuracy for the Gaussian/Bayesian methods.

**Evidence limits.** A Windows progress-file replacement error interrupted the campaign. Its source-freeze criterion was also not met: an equivalent lambda-to-function rewrite occurred during execution, without per-worker source hashes. The repaired-source smoke is a separate experiment and does not retroactively validate the interrupted run. Raw chains were not saved, so recorded energy/CRPS and interval bounds cannot be independently recomputed from point summaries. Calibration and scores on successful cases must be read alongside the failures.

Evidence: [full conclusions and paired score table](RESEARCH_CONCLUSIONS.md), [recovered analysis](../../results/followup-20261021/research-recovered/analysis.md), [corrected-source smoke report](../../results/followup-20261021/smoke-repaired/report.md), [requirement audit](../../.scratch/bila-kde-validation/final-audit.md).

## 4. Live issue dashboard

**Done.** Delivered a read-only local dashboard backed by Markdown issues: four epics, completed implementation history, status/search filters, task details, Board/List views and a Dependency graph with prerequisite arrows, context nodes, zoom and cycle handling. The collapsible campaign thread shows timestamped explanations, outcomes and next steps, preserves reading state and refreshes automatically.

**Tested.** Dashboard verification records **38 Python tests passed / 1 OS-dependent skip**, **7 Node tests passed** and **12 Chromium scenarios passed**, with desktop/mobile inspection and independent review. Checks cover source reconciliation, path confinement, malformed data, filters, details, graph behavior and retained UI state. Dashboard Python tests are included in the combined repository suite above; these totals must not be added together as independent tests.

**Conclusion.** The monitor provides a verified view of recorded task and campaign evidence. A stale progress file is not proof that a worker is still running; interrupted and unreached work remain explicit. Local-only operation and read-only issue access are intentional limits.

Open [the running local dashboard](http://127.0.0.1:8765), or start it with `uv run python -m scripts.issue_dashboard --open`. Evidence: [dashboard usage and checks](../../.scratch/issue-dashboard/README.md), [delivery ledger](../../.scratch/issue-dashboard/ledger.md).

## Recommended next step

Investigate **why 100-point KDE bridges cannot reach the required Monte Carlo precision within 60 seconds**. Use a small fixed set of cases to separate density-evaluation cost from mixing and summary precision, preserving the target law and acceptance thresholds. Then consider a separately budgeted, immutable-source comparative campaign with adequate replication. Explicit dependence, density-estimation uncertainty and real-data evaluation remain later extensions.

Primary mathematical and software foundations: [REFERENCES.md](REFERENCES.md). Earlier 28-issue closure snapshot (before the per-epic dashboard addition): [final-state.json](../../.scratch/bila-kde-validation/evidence/final-state.json).
