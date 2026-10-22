# Next investigation: native kernels and trajectory budgets

Status: documented and planned; no native implementation or smaller-ensemble trial has run.

The previous long-gap investigation tested an isolated NumPy temporary-buffer candidate at 24,000 paths. It passed 41 correctness checks, preserved four shorter successes and rescued none of the eight 100-point applications. The result supports investigating a different computational approach or output size; it does not show that the conditional KDE model is mathematically unable to bridge longer gaps.

The next epic separates **requested ensemble size** from **numerical engine**. The human selected Python versus one native implementation at **4,000, 8,000 and 24,000 paths**, with a **60-minute experiment cap**. Build/setup time is recorded separately. The canonical local decision map and exact schedule are [under scratch](../../.scratch/bila-kde-native-kernels/map.md), with [the full protocol](../../.scratch/bila-kde-native-kernels/plan.md). Those operational files remain local, as explained in [the documentation index](../README.md).

## Why fewer paths could help

The current sampler requests four chains and begins its first convergence assessment after obtaining the requested retained block per chain. At 24,000 total paths that block is 6,000 draws per chain; at 8,000 it is 2,000, and at 4,000 it is 1,000. Warmup and the maximum update cap remain separate. A smaller request allows earlier assessment, but the sampler can still continue or fail if the block does not meet the original diagnostics.

The fitted density and endpoint-conditioned target do not change with requested output size. Monte Carlo precision does: smaller correlated ensembles may have insufficient effective sample size or unreliable tail quantiles. The experiment therefore retains the existing R-hat, bulk/tail ESS, mean MCSE and quantile MCSE thresholds, including every original interval level. A smaller loop finishing is not sufficient evidence of a successful reconstruction.

Historical 24,000-path results remain labeled. No result from the proposed smaller-output configurations exists yet. Scores from different ensemble sizes also have different Monte Carlo error and must not be used as an unqualified predictive-quality ranking.

## Why a native kernel might help

The measured profiles put most sampler work in Gaussian-mixture evaluation and conditional kernel-label refresh. A native implementation could fuse standardization, stable exponentiation/reduction and categorical calculations, reducing intermediate arrays and repeated memory passes. This is a hypothesis about the measured computation, not an assumed C++/Rust speed multiplier.

NumPy already implements many universal functions in compiled C. Consequently, translating the same array-operation sequence into another language may provide little benefit; the proposed change must reduce actual work or memory traffic. Kernel throughput, binding/conversion cost and complete-application time must be measured separately. [NumPy ufunc implementation overview](https://numpy.org/doc/stable/user/basics.ufuncs.html), [output and overlapping-memory behavior](https://numpy.org/doc/stable/reference/ufuncs.html).

## Binding options

| Route | Relevant capability | What remains to establish |
|---|---|---|
| C++ with nanobind | Native functions can exchange NumPy arrays through its ndarray interface, including zero-copy protocols. | A working Windows/Python build, strict array contracts, useful operation fusion and measured full-application benefit. |
| Rust with PyO3 and rust-numpy | PyO3 creates native Python extension modules; rust-numpy supplies NumPy array/C-API interfaces. | Toolchain/setup cost, safe ownership/borrowing, equivalent numerical behavior and measured benefit. |

Primary documentation: [nanobind ndarray interface](https://nanobind.readthedocs.io/en/latest/ndarray.html), [PyO3 extension guide](https://pyo3.rs/), [rust-numpy API](https://docs.rs/numpy/latest/numpy/).

Only one native route is included in this epic. Local inspection found Visual Studio 2022 Build Tools with the VC component and bundled CMake. These tools were not exposed on the current PATH; their presence is not proof an extension can be built/imported. Cargo was not found on PATH or in the usual user location. **C++/nanobind is therefore the initial setup recommendation**, while the human language/build decision remains open. No performance comparison between C++ and Rust has been made.

## Boundary and scientific safeguards

Keep the Python public API, fitting rules, target correction, four Gibbs sweeps, diagnostics and resource supervision. The experimental extension should expose a small float64 batch interface for the measured kernels, with explicit ownership, stride/contiguity and mutation behavior. Conversion and dispatch costs count in its performance result.

Initially retain NumPy random streams and provide recorded variates or labels to native calculations. This avoids changing the RNG at the same time as the numerical engine. Freeze operation/tolerance requirements before execution; disable relaxed fast-math, and preserve zero-weight and extreme-scale behavior. Exact path-bit equality is not universally expected when reduction arithmetic changes, so independent conditional-law and numerical-reference checks remain essential.

The production package remains Python/NumPy until an experimental backend earns a separate reviewed integration handoff. A native microbenchmark win is insufficient if the full reconstruction still times out or fails precision.

## Planned comparison and possible conclusions

The main panel has two independent series each for Gaussian and changing-shape 100-point settings. Cross both methods, three counts and two engines: **48 long-gap applications**. Add four 8,000-path shorter regression controls, for **52 applications** in total. This is an exploratory engineering screen with two replications per long-gap setting, not a broad predictive study.

The 60-minute experiment budget reserves three minutes for correctness, two for kernel/binding probes, 52 for full applications and three for finalization. Each complete application remains capped at 60 seconds and 2 GiB. Setup/build has its own recorded ceiling to settle before execution. Failed checks, build failures, timeouts and untested identities remain visible; no automatic retries or budget extensions occur.

The final decision can support smaller Python ensembles, native acceleration at a matched count, both, or neither. The experiment must distinguish those explanations. If smaller Python ensembles already meet the required quality, native packaging cost may be unjustified. If native code helps, report rescued paired applications and complete-application effects before proposing integration. Any success remains specific to this panel and the declared quality contract.

Previous scientific limitations and mathematical foundations remain in [the research conclusions](RESEARCH_CONCLUSIONS.md) and [references](REFERENCES.md). This note adds prospective engineering choices, not new claims of sampler accuracy or predictive superiority.
