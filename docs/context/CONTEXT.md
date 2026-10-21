# BiLA-KDE Bridge

Probabilistic reconstruction of missing intervals in univariate time series using local kernel density estimates and endpoint-constrained trajectories.

## Language

**Internal gap**:
A contiguous sequence of missing observations bounded by an observed value on each side.

**Observed neighborhood**:
A sequence of genuinely observed values on one side of a gap, used to estimate the local stochastic behavior.

**Endpoint-corrected bridge**:
A random trajectory adjusted to meet both observed endpoints; endpoint matching alone does not make it a draw from the conditioned innovation model.
_Avoid_: Conditioned bridge when referring only to endpoint correction.

**Conditioned bridge**:
A trajectory governed by the stochastic model's conditional law given both observed endpoint values.
_Avoid_: Endpoint-corrected bridge as a synonym.

**Bidirectional time-varying KDE**:
An innovation density that blends separate estimates from the left and right observed neighborhoods with weights that vary across the gap.

**Pooled KDE**:
A single innovation density estimated from the combined left and right observed neighborhoods.

**First-order dependent increments**:
An increment process whose next-increment distribution depends on the immediately preceding increment. This differs from dependence on the preceding series level.

**Independent-increment model**:
A stochastic model whose increments are independent before endpoint conditioning, with distributions that may vary across time. Its conditioned bridge generally has dependent increments.

**Path uncertainty conditional on fitted KDEs**:
Variability in the missing trajectory when the estimated increment densities and observed endpoints are held fixed. It excludes uncertainty about the estimated densities themselves.

**Temporal density blending**:
A prescribed change in the relative contributions of the left and right innovation densities across a gap. Fixed blending does not imply that the weights were learned from data.
