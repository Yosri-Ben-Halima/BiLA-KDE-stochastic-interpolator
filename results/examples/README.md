# Final example outputs

Start with the [compact styled GIF](distribution_evolution_styled.gif) or the [before/after gallery](before_after.png).

| Files | Purpose |
| --- | --- |
| `distribution_evolution_styled.gif` | Compact animation of the third example. |
| `before_after.png` | Three examples, each with before/after views and a gap close-up. |
| `diagnostics.json` | Sampling checks, requested sample counts, and interval statuses. |

The ensembles contain 24,000 paths each. Bands are 95% for examples 1 and 2, and 90% for example 3. Its failed 95% check remains in the diagnostics. The styled animation focuses on example 3. Each series has one internal ten-value gap. Hidden truth is used only for comparison; the imputer receives the masked input. Generation scripts are in `examples/` at the repository root. Intermediate NPZ data and the older GIF were removed; regenerating visuals requires generating samples again.

The blue band is a pointwise interval at the coverage stated in its panel title, conditional on fitted KDEs, not a simultaneous whole-path band or an interval for density-estimation uncertainty. These three illustrations do not measure predictive calibration or superiority. Diagnostics and any failures are in diagnostics.json. Failed quantile checks suppress bands.
