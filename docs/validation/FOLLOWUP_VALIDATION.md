# Tail precision and runtime follow-up — 21 October 2026

## Current state after the interruption

The research process stopped with WinError 5 while replacing `progress.json`, after 792 attempted applications. Original files are preserved at `results/followup-20261021/research/`; their manifest remains the raw running-state file left by the crash. Use the separate [recovered terminal audit](../../results/followup-20261021/research-recovered/analysis.md) for authoritative accounting: **691 successful artifacts audited, 101 timeouts, 4,368 untested applications**. No sampling was resumed and no second four-hour campaign was started. Last telemetry was 13,810.48 seconds; it is not an independently measured total process runtime.

An initial 24-file snapshot remains intact, but the source-freeze criterion was violated by a local lambda-to-equivalent-function rewrite in `sampling.py` during execution. The initial signature is `ca1cdbbb0259b8b1a17c84f9eae2f7c8c0e4d4e6bc114392b13ed679a2a9df23`; the observed post-interruption signature was `f477d624187236d415dad5ac419dbe0ae504bd474317e42825b31e8f4ac6cf19`. Only that style rewrite differed at the post-run inspection, and the operations are unchanged, but per-application source hashes are unavailable. Do not present this as one unchanged execution version. [Interruption evidence](../../results/followup-20261021/review/campaign-interruption.json) records the comparison and a matching Windows reader-lock reproduction; the reader responsible for the original failure was not identified.

After termination, integrated the reviewed density repair and a bounded publication retry. The full suite passed **125 tests / one Windows fixture skip in 99.18 seconds**, including performance headroom; lint and sdist/wheel build passed. A real Windows release-after-50-ms probe published successfully in 0.074 seconds. Persistent publication failure still raises and retains the old complete JSON and temporary evidence. A focused independent review found no actionable issue in the repairs or recovered provenance.

The corrected execution source is archived at [source-repaired](../../results/followup-20261021/source-repaired/snapshot.json), signature `c57a22862ea9eb6d488f8fad0c5c49a8363e0a1da3e4419fd04bf5aef419c8d8`. The fresh [smoke-repaired](../../results/followup-20261021/smoke-repaired/report.md) stage passed **51/51 in 657.07 seconds**, with all 15 references and 36 method applications successful under the original configuration, 30-minute cap, requested quantiles and per-application limits. The [terminal artifact audit](../../results/followup-20261021/smoke-repaired/artifact-audit.json) reconciles all outcomes, exact planned identities, all 36 saved predictions and all 24 live/archived source/configuration hashes. Peak recorded process memory was 288.21 MiB. No illustrative interval fallback or raw-chain NPZ output was used. Earlier evidence below describes earlier versions and remains distinct from this source-specific result. The supported interpretation and next investigation are in [RESEARCH_CONCLUSIONS.md](../research/RESEARCH_CONCLUSIONS.md).

## Scope and fixed requirements

Investigate the inconclusive displaced-mixture tail reference, reduce longer-gap computation, and complete current-source smoke validation. Preserve fitted target laws, Scott bandwidths, linear blending, endpoint invariants, 60-second/2-GiB per-application limits, existing diagnostics and all requested quantiles. Use the unchanged `benchmarks/validation.toml` (24,000 predictive paths and 32,000 reference paths). No 90% fallback in scientific evaluation. Retain original evidence and avoid NPZ files.

## Diagnosis recorded before the new smoke run

The original tail failure was reproduced by `tests/test_tail_reference.py` with seed 2026. A fixed three-seed investigation (2026–2028, 32,000 paths each) compared the elliptical-only sampler with independent draws from the exactly enumerated 16-component conditional mixture. All three original chains were inconclusive on the tail screen; all three independent-mixture ensembles passed. Mean/covariance errors were small. These results support insufficient tail precision in this transition at the declared count; they do not prove the absence of all bias or establish a target-law defect.

Profiling the unchanged AR-gap fixture at 8,000 requested paths and 2,000 retained updates per chain recorded 37.08 seconds. Repeated log-sum-exp work consumed 20.25 seconds cumulatively, including overlapping callers. Source snapshots and diagnostic output are in `results/followup-20261021/source-before/`, `profile-before/`, and `tails-before/`.

## Changes under test

- Cache Gaussian kernel centers, variances and temporal log weights. Compute the same Gaussian mixture density with a stable maximum-shifted exponential sum, avoiding repeated general-purpose log-sum-exp overhead. Algebraically collapse duplicated KDE components in pooled/one-sided controls. No kernel truncation or approximate density interpolation.
- Sample conditional kernel labels with an unnormalized cumulative exponential sum, requiring one exponential evaluation rather than two. Gaussian sum conditioning and the four Gibbs sweeps remain unchanged. A new edge-case regression prevents an exactly zero uniform variate selecting a zero-probability component.
- Share this cached mixture engine between fitted KDEs and the frozen two-component reference. All four frozen-mixture references now exercise the complete current production transition (ellipse plus four conditional Gibbs sweeps), while their analytic laws remain independently specified and enumerated. The earlier elliptical-only reference remains reproducible using `benchmarks.diagnose_tail --elliptical-only`; its unsuccessful evidence is not removed or reclassified.
- Record per-coordinate tail errors and MCSEs in new reference diagnostics, in addition to their maxima.

Frozen-formula tests cover zero weights, extreme inputs, unequal observed windows, and every KDE ablation. Exact-Gaussian and exact-mixture transition tests check law preservation. After optimization, the same profiler command recorded 12.44 seconds; the same three-seed tail investigation passed all three cases. Timing includes profiling overhead and is specific to this laptop. This evidence motivates, but does not replace, the original 24,000-path/60-second regression and complete smoke stage.

## Declared validation sequence

1. Measure the archived original density implementation against the full longer-gap contract, then verify the optimized implementation. The first direct archived run passed the 60-second limit in 53.01 seconds under today's conditions; this does not reproduce the previous watchdog timeout on an idle system. To protect against load/startup variation, the runtime regression additionally requires completion with 20 seconds of headroom (less than 40 seconds), a stricter software performance check that does not relax the scientific 60-second limit. Verify this stricter regression against both implementations. Run the full software suite, lint and build.
2. Freeze source/configuration and run one complete smoke stage with the original 30-minute cap, all 15 references and all 36 method applications, unchanged order/seeds and unchanged complete-method-block reservation rule. Save JSON summaries and all unsuccessful statuses.
3. Inspect references, tail bounds, successful outputs, resource limits, untested cases and source signatures. A passing stage gate is not a claim of universal sampling reliability or predictive superiority. Any remaining failures must be reported and investigated as necessary; no automatic statistical rerun merely to obtain a pass.
4. Only after validated smoke evidence, the previously budgeted research comparison may run under its separate four-hour ceiling, retaining failed and unreached cases. Report achieved replication counts explicitly rather than claiming the target of 30 independent series per primary cell was guaranteed.

```powershell
uv run python -m benchmarks.diagnose_sampling --output results/followup-20261021/profile-after
uv run python -m benchmarks.diagnose_tail --output results/followup-20261021/tails-after
uv run pytest -q
uv run python benchmarks/run.py --stage smoke --config benchmarks/validation.toml --output results/followup-20261021/smoke
```

Existing diagnostic directories are not overwritten. Both sampling algorithms share the same frozen target in the three-seed comparison; the production transition changes the Monte Carlo exploration rather than the reference quantiles or tolerances.

## Recorded smoke outcome

All 63 software tests passed in 84.51 seconds; lint and package build passed. The archived implementation failed the new headroom regression at 50.40 seconds, while the optimized version passed. All three declared hybrid-transition tail checks passed against the unchanged exact target.

The fresh smoke stage passed **51/51 applications in 589.36 seconds**, with all 15 references and all 36 method applications successful. No tolerances or per-application limits were relaxed, no quantile fallback was used, and the source signature matches the executed manifest. This satisfies the defined smoke gate. The research stage was then started under the separate 14,400-second cap using this exact source/configuration and smoke parent; it later terminated with the interruption and source-provenance limitations recorded above. See [VERIFICATION.md](VERIFICATION.md) and the machine-recorded research artifacts for completion status and achieved replication counts.

## Post-run analysis preparation

While the campaign runs, inference and benchmark-execution source files remain frozen. The separate `scripts/research_summary.py` reporter has six passing focused tests. It preserves paired-case matching, unsuccessful counts, prior-sensitivity variants, and the full six-cell adaptation definition; it does not average away missing adaptation cells. Its artifact audit independently reconciles observed-data hashes, gap/endpoints, RMSE/MAE, and coverage counts. All 36 successful smoke prediction artifacts passed this audit (`smoke/artifact-audit.json`). Energy/CRPS and interval bounds cannot be independently reconstructed without raw chains, which are not retained under the requested JSON-only policy.

After the research manifest is terminal, run:

```powershell
uv run python -m scripts.research_summary results/followup-20261021/research
```

This writes descriptive analysis, actual replication counts, method reliability, matched energy differences and coarse Monte Carlo uncertainty alongside the unmodified run evidence. It refuses to label an ongoing run final. These post-processing files do not change the executed source/configuration signature or any sampled prediction.

## Independent review during the frozen research run

A read-only review found that the terminal reporter checked record count rather than exact planned `(case, method)` identities. A replacement unplanned method could conceal a missing planned method. A regression reproduced that acceptance; the reporter now checks the exact manifest application set and rejects missing or unexpected records. All nine reporter tests pass, including separate missing/replaced/extra application cases. At that review checkpoint the sampling and benchmark-execution source was unchanged; the later style rewrite is documented in the current-state section above.

The review also found two extreme-scale numerical regressions in the cached density: squaring raw differences can overflow before bandwidth standardization, and reconstructing bandwidths from subnormal variances can alter the fitted density. Both are independently reproduced in `review/density-before.json` using `scripts.review_density`; an ordinary-scale control agrees. These findings qualify the earlier same-density claim over the full accepted input range. They were staged for repair after the research process ended; their integration and full software checks are now recorded above. The existing smoke evidence covers its specified fixtures, not these extreme scales. Campaign manifests must retain their original source signature; a repaired source will require fresh validation evidence, not relabeling of old runs.

The initial candidate repair was staged separately in `review/candidate-src/`, with its patch and hashes in `review/density-fix.patch` and `review/candidate.json`. Twelve review regressions fail on the unchanged executed source. The isolated candidate passes these plus the existing density/kernel tests (**29 passed in 2.78 seconds**). It standardizes before squaring, preserves the original KDE bandwidth for density normalization and Gaussian draws, and rescales variance ratios before sum conditioning. The latter also fixes a reproduced variance-sum overflow in the internal Gaussian mixture engine. Those were candidate-only results at review time; integration, complete software checks and source-specific validation are recorded in the current-state section above. No heavy performance/sampling tests were run concurrently with the resource-bounded research campaign.

The initial execution Python source and configuration are preserved in `source-executed/`, with independently verified source signature `ca1cdbbb0259b8b1a17c84f9eae2f7c8c0e4d4e6bc114392b13ed679a2a9df23`. This defines the initial execution version; the observed later style change is separately preserved and prevents claiming one unchanged per-worker version.

An interim integrity audit checked the first 104 complete research journal records: 91 successful saved artifacts passed observed-data, endpoint, point-error and coverage-count reconciliation; 13 time-limit outcomes remained present. The audit also verified planned application membership and the unchanged executed source signature (`review/progress-artifact-audit.json`). This is a frozen prefix audit, not the terminal campaign result or a comparative conclusion. The recovered terminal audit is now linked above.

## Interactive workstation context

A later frozen-prefix audit at 10:58 UTC checked 531 complete journal records: all 464 successful prediction artifacts passed the same independent reconciliation, and 67 time-limit outcomes remained present (`review/progress-artifact-audit-0531.json`). The journal prefix hash and byte length identify exactly what was checked. A separate 24-file audit verified both current and archived source/configuration bytes against the preserved snapshot (`review/live-source-audit.json`). These checks establish interim integrity, not a completed campaign or comparative advantage.

During the campaign the user requested scratch issue history and a live local monitoring dashboard. That work used lightweight Python/JavaScript checks and several short Chromium verification runs on this same laptop; the dashboard continues to serve and refresh locally. No heavy scientific or performance suite was run concurrently, and seeds, limits and thresholds remained unchanged. The later source inspection identified the sampling.py style rewrite documented above. Wall-clock measurements therefore describe this interactive workstation, not a dedicated idle benchmark host. Preserve resource failures and qualify any runtime comparison with this context; do not infer that every timeout is intrinsic algorithm cost or that other activity caused a particular failure.
