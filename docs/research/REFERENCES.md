# References

Scientific foundations and primary implementation references for BiLA-KDE Bridge. Links and their relevance were checked on **20 October 2026**. This is a bibliography of the methods used or investigated, not evidence that this prototype outperforms competing imputers. Numerical results belong in [VERIFICATION.md](../validation/VERIFICATION.md) and the corresponding run artifacts.

Maintain this file when adding or replacing a density estimator, transition kernel, diagnostic, baseline, or score. Record what the reference supports and distinguish implemented methods from possible extensions. Dependency versions are recorded in `uv.lock`; linked software documentation may describe a different release.

Implementation mapping updated on **21 October 2026**: fitted KDEs and frozen reference mixtures share a cached finite-Gaussian-mixture engine. Maximum-shifted exponential sums and collapsed duplicate components are algebraic optimizations of the same densities; they do not introduce a new estimator, bandwidth, or truncated target. Both mixture-reference families now exercise the full elliptical-plus-Gibbs transition, with the original elliptical-only version retained as a diagnostic ablation. The conditioning and augmentation foundations remain entries 5–7 below.

The final numerical repair preserves the original kernel bandwidths, standardizes before squaring and conditions using relative variances at extreme scales. This changes numerical evaluation rather than the statistical model; no new mathematical foundation is introduced. Evidence and the interrupted campaign's limits are recorded in [RESEARCH_CONCLUSIONS.md](RESEARCH_CONCLUSIONS.md).

## Density estimation

1. **Rosenblatt, M. (1956).** “Remarks on Some Nonparametric Estimates of a Density Function.” *The Annals of Mathematical Statistics*, **27**(3), 832–837. [Publisher / DOI](https://doi.org/10.1214/aoms/1177728190).
   Historical foundation for kernel density estimation, used for observed forward-increment densities in `src/bilakde/density.py`. The paper does not propose the bidirectional endpoint-conditioned construction used here.

2. **Parzen, E. (1962).** “On Estimation of a Probability Density Function and Mode.” *The Annals of Mathematical Statistics*, **33**(3), 1065–1076. [Publisher / DOI](https://doi.org/10.1214/aoms/1177704472); [paper](https://bayes.wustl.edu/Manual/parzen62.pdf).
   KDE foundation. Classical independent, identically distributed sampling theory does not automatically justify fitting a stationary density to a changing local increment distribution.

3. **Scott, D. W. (1992).** *Multivariate Density Estimation: Theory, Practice, and Visualization*. Wiley, especially Chapter 6, “Kernel Density Estimators.” [Book / DOI](https://doi.org/10.1002/9780470316849); [chapter](https://doi.org/10.1002/9780470316849.ch6).
   Basis for the deterministic bandwidth convention. The implemented univariate rule is **`h = s * n**(-1/5)`**, with sample standard deviation `s` (`ddof=1`), separately for each fitted side. It is not Silverman’s robust `0.9 * min(s, IQR/1.34) * n**(-1/5)` rule.

4. **SciPy developers.** [`scipy.stats.gaussian_kde` documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.gaussian_kde.html).
   Primary software reference for Scott’s factor `n**(-1/(d+4))` and Gaussian-kernel bandwidth conventions. Production KDE evaluation is implemented locally; this citation does not mean inference delegates to SciPy’s KDE object.

## Conditioning, bridges, and sampling

5. **Rasmussen, C. E., and Williams, C. K. I. (2006).** *Gaussian Processes for Machine Learning*. MIT Press. [Author-hosted book](https://gaussianprocess.org/gpml/); [Appendix A.1](https://gaussianprocess.org/gpml/chapters/RWA.pdf), particularly equation A.6; [Chapter 2](https://gaussianprocess.org/gpml/chapters/RW2.pdf), equations 2.18–2.19.
   Gaussian conditioning identities underlying `src/bilakde/gaussian.py`, Gaussian reference bridges, conditional kernel refreshes, and Gaussian validation oracles. For independent Gaussian increments with mean vector `mu`, variance vector `v`, and fixed sum `d`, these identities give conditional mean `mu + v * (d - sum(mu)) / sum(v)` and covariance `diag(v) - outer(v,v) / sum(v)`. The homoskedastic random-walk case yields the discrete Brownian-bridge covariance. This project does not implement a general Gaussian-process imputer.

6. **Murray, I., Adams, R. P., and MacKay, D. J. C. (2010).** “Elliptical slice sampling.” *Proceedings of AISTATS*, PMLR **9**, 541–548. [Proceedings and paper](https://proceedings.mlr.press/v9/murray10a.html).
   Basis of the elliptical slice transition in `src/bilakde/sampling.py`. We factor the fitted KDE bridge target into a Gaussian bridge reference and a target/reference density correction. The Gaussian reference alone is not the fitted KDE law. Invariant-law arguments do not guarantee adequate finite-budget mixing.

7. **Tanner, M. A., and Wong, W. H. (1987).** “The Calculation of Posterior Distributions by Data Augmentation.” *Journal of the American Statistical Association*, **82**(398), 528–540. [Publisher / DOI](https://doi.org/10.1080/01621459.1987.10478458).
   General foundation for latent-variable augmentation. The current implementation introduces Gaussian KDE kernel labels: sample labels conditional on increments, then jointly sample Gaussian increments conditional on those labels and their endpoint sum. This composition with elliptical slice moves is our implementation of standard augmentation and conditioning principles; this paper does not specify this particular BiLA-KDE sampler.

8. **Särkkä, S. (2013).** *Bayesian Filtering and Smoothing*. Cambridge University Press, IMS Textbooks **3**. [Author-provided book](https://users.aalto.fi/~ssarkka/pub/cup_book_online_20131111.pdf); [publisher front matter](https://assets.cambridge.org/97811070/30657/frontmatter/9781107030657_frontmatter.pdf).
   Mathematical background for Gaussian state-space conditioning and smoothing baselines. In `benchmarks/bayesian.py`, observations are noiseless, the local-level model is a Gaussian random walk, and AR(1) paths use conditional Gaussian transitions. The implementation uses specialized bridge formulas rather than a general Kalman/forward-filtering backward-sampling engine.

## MCMC reliability and numerical precision

9. **Vehtari, A., Gelman, A., Simpson, D., Carpenter, B., and Bürkner, P.-C. (2021).** “Rank-Normalization, Folding, and Localization: An Improved R-hat for Assessing Convergence of MCMC (with Discussion).” *Bayesian Analysis*, **16**(2), 667–718. [DOI](https://doi.org/10.1214/20-BA1221); [authors’ preprint](https://arxiv.org/abs/1903.08008).
   Basis for rank-normalized split R-hat, bulk/tail effective sample size, and inspecting more than a posterior mean. `src/bilakde/diagnostics.py` checks interior levels and selected path functionals across four chains. Passing the screen is evidence against detected nonconvergence, not proof of convergence or predictive calibration.

10. **ArviZ developers.** Versioned 0.22 API documentation: [`rhat`](https://python.arviz.org/en/v0.22.0/api/generated/arviz.rhat.html), [`ess`](https://python.arviz.org/en/v0.22.0/api/generated/arviz.ess.html), and [`mcse`](https://python.arviz.org/en/v0.22.0/api/generated/arviz.mcse.html).
    Primary implementation references for the diagnostic calls and mean/quantile Monte Carlo standard errors used in `diagnostics.py` and `results.py`. The repository’s acceptance limits—including quantile MCSE no larger than 10% of local standard deviation—are explicit project choices; the documentation does not establish them as universal guarantees. Quantile precision measures simulation error, not uncertainty from estimating KDEs or empirical interval coverage.

## Bayesian competitors

11. **Murphy, K. P. (2007).** “Conjugate Bayesian analysis of the Gaussian distribution.” Technical report, 3 October 2007. [Author-hosted report](https://www.cs.ubc.ca/~murphyk/Papers/bayesGauss.pdf).
    Foundation for inverse-gamma variance and conditional normal/inverse-gamma calculations in `benchmarks/bayesian.py`. The benchmark’s priors, marginalized gap likelihood, and quadrature grid are repository-specific choices and must be read from that code/configuration.

12. **Stan Development Team.** *Stan User’s Guide*: [Time-Series Models](https://mc-stan.org/docs/stan-users-guide/time-series.html) and [Missing Data](https://mc-stan.org/docs/stan-users-guide/missing-data.html).
    Primary modeling references for autoregression and conditioning/integrating over unobserved quantities. The implemented Bayesian AR(1) competitor marginalizes gap transitions and uses checked one-dimensional quadrature for the AR coefficient, with conditional parameter/path draws. It does not use Stan, HMC, or a fitted observation-noise model. Fixed-parameter counterparts are ablations, not full Bayesian parameter integration.

## Probabilistic evaluation and deterministic controls

13. **Gneiting, T., and Raftery, A. E. (2007).** “Strictly Proper Scoring Rules, Prediction, and Estimation.” *Journal of the American Statistical Association*, **102**(477), 359–378. [Publisher / DOI](https://doi.org/10.1198/016214506000001437); [author-hosted paper](https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf).
    Basis for CRPS and the multivariate energy score in `benchmarks/scoring.py`. Here energy score is computed on the missing path vector and normalized by the square root of its dimension; marginal CRPS is averaged over missing positions. Finite-ensemble estimates and coarse Monte Carlo uncertainty diagnostics are implementation choices. Proper scoring in expectation does not certify calibration from a few illustrated trajectories.

14. **Scheuerer, M., and Hamill, T. M. (2015).** “Variogram-Based Proper Scoring Rules for Probabilistic Forecasts of Multivariate Quantities.” *Monthly Weather Review*, **143**(4), 1321–1334. [NOAA record and paper](https://repository.library.noaa.gov/view/noaa/22327/); [DOI](https://doi.org/10.1175/MWR-D-14-00269.1).
    Basis for the variogram score accompanying energy score, because energy score can be less sensitive to dependence errors. The implementation uses exponent 0.5, selected lags, and inverse-lag weights. Variogram score is proper but does not uniquely identify every possible path distribution.

15. **Fritsch, F. N., and Butland, J. (1984).** “A Method for Constructing Local Monotone Piecewise Cubic Interpolants.” *SIAM Journal on Scientific and Statistical Computing*, **5**(2), 300–304. [Publisher / DOI](https://doi.org/10.1137/0905021).
    Algorithmic reference cited by SciPy for the shape-preserving PCHIP control actually used in `benchmarks/methods.py`. This deterministic control supplies point predictions rather than a probabilistic path ensemble.

16. **SciPy developers.** [`PchipInterpolator` documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.PchipInterpolator.html).
    Primary software description of the interpolator used by the benchmark, including derivative selection and endpoint treatment. This is the direct implementation reference for entry 15.

17. **Fritsch, F. N., and Carlson, R. E. (1980).** “Monotone Piecewise Cubic Interpolation.” *SIAM Journal on Numerical Analysis*, **17**(2), 238–246. [Publisher / DOI](https://doi.org/10.1137/0717021).
    Earlier mathematical context for monotonicity-preserving cubic interpolation. Do not conflate its algorithm with the Fritsch–Butland derivative construction documented for SciPy’s current PCHIP control.

## Investigated extensions; not implemented in the public model

18. **Bashtannyk, D. M., and Hyndman, R. J. (2001).** “Bandwidth selection for kernel conditional density estimation.” *Computational Statistics & Data Analysis*, **36**(3), 279–298. [Author page, paper, and erratum](https://fpp.robjhyndman.com/publications/bandwidth-selection-for-kernel-conditional-density-estimation/); [DOI](https://doi.org/10.1016/S0167-9473(00)00046-3).
    Foundation considered for previous-increment-dependent KDE in the feasibility investigation. The released model uses independent increments before endpoint conditioning. Independent-observation asymptotics do not automatically cover overlapping lag pairs.

19. **Lindsten, F., Jordan, M. I., and Schön, T. B. (2014).** “Particle Gibbs with Ancestor Sampling.” *Journal of Machine Learning Research*, **15**(63), 2145–2184. [Journal and paper](https://jmlr.org/papers/v15/lindsten14a.html).
    Investigated alternative for trajectory sampling with explicit temporal dependence. Particle Gibbs/ancestor sampling is not the current sampler; its theoretical results are not validation of this implementation.

20. **Del Moral, P., and Murray, L. M. (2015).** “Sequential Monte Carlo with Highly Informative Observations.” *SIAM/ASA Journal on Uncertainty Quantification*, **3**(1), 969–997. [Publisher / DOI](https://doi.org/10.1137/15M1011214); [authors’ preprint](https://arxiv.org/abs/1405.4081).
    Investigated background on guided particle methods and bridge simulation under informative endpoint observations. These methods remain alternatives; this project does not implement their SMC bridge or inherit their empirical performance results.

## Resampling and model-mismatch stress tests

21. **Efron, B., and Tibshirani, R. J. (1993).** *An Introduction to the Bootstrap*. Chapman & Hall, Monographs on Statistics and Applied Probability **57**, especially Chapters 11 (jackknife) and 13 (percentile intervals). [Publisher page](https://www.routledge.com/An-Introductionto-the-Bootstrap/Efron-Tibshirani/p/book/9780412042317). The publisher's current listing dates the paperback to 1994; the first publication was 1993.
    General foundation for two separate uncertainty calculations. In `benchmarks/scoring.py`, deleting each of four independently seeded chain groups gives a **coarse, project-specific four-group jackknife MCSE** for energy/CRPS estimates, with pair-selection error reported separately; the textbook does not validate this particular finite-chain estimator. In `benchmarks/runner.py`, 2,000 resamples of paired BiLA-minus-pooled score differences provide exploratory percentile intervals across independently generated series within each setting; the adaptation contrast resamples within its six cells. These intervals describe the jointly successful subset and do not correct for selective method failure. Series-level bootstrap replication must not be confused with resampling correlated MCMC trajectories as if they were independent observations.

22. **Bollerslev, T. (1986).** “Generalized autoregressive conditional heteroskedasticity.” *Journal of Econometrics*, **31**(3), 307–327. [Publisher / DOI](https://doi.org/10.1016/0304-4076(86)90063-1); [author's institutional publication record](https://scholars.duke.edu/publication/651658).
    Foundation for the GARCH(1,1) increment generator in `benchmarks/scenarios.py`: conditional variance `h_t = 0.05 + 0.10 * r_(t-1)**2 + 0.85 * h_(t-1)` and Gaussian standardized innovations, after burn-in. This is solely a model-mismatch stress generator; BiLA-KDE does not fit GARCH or explicitly model this volatility dependence.

## Scope of attribution

The observed-increment window rules, linear left/right mixture schedule, benchmark priors, resource limits, diagnostic thresholds, and exact combination of transitions are specified by this repository. The references above supply mathematical building blocks and related methods; none alone establishes the full BiLA-KDE construction as novel, correctly implemented, or scientifically superior. In particular, the present plug-in KDE bridge does not propagate uncertainty in fitted density estimates or bandwidths.
