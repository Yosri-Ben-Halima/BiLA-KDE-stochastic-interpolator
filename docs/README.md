# Documentation

| Area | Documents |
|---|---|
| Usage | [Detailed guide](usage/guide.md), [visual examples](../results/examples/README.md) |
| Context and mathematics | [Domain terminology](context/CONTEXT.md), [original proposal](context/formalisation.md) |
| Research | [Executive summary](research/EXECUTIVE_SUMMARY.md), [conclusions](research/RESEARCH_CONCLUSIONS.md), [references](research/REFERENCES.md) |
| Validation | [Verification record](validation/VERIFICATION.md), [predeclared protocol](validation/STEP1_VALIDATION.md), [follow-up investigations](validation/FOLLOWUP_VALIDATION.md) |

The original proposal describes a broader research direction. The root [README](../README.md) and detailed guide identify the implemented independent-increment prototype and its limits.

## Public documentation and local evidence

Project-level Markdown formerly scattered at the repository root is grouped in these subdirectories. The root `README.md` remains the landing page; `CLAUDE.md` and `AGENTS.md`, if added, can remain at the root. Contextual README files stay beside the material they describe.

Historical reports retain links to local evidence under `results/` and private issue history under `.scratch/`. Those directories contain generated measurements, immutable execution snapshots and live operational state; they are excluded from the public repository, apart from the curated example gallery. Such paths are useful in the original research workspace and will not resolve in a fresh public checkout. Published conclusions preserve their limitations and do not turn unavailable raw evidence into a reproducibility claim.

To generate new measurements, follow the benchmark commands in the detailed guide. Do not overwrite a prior run's output directory.
