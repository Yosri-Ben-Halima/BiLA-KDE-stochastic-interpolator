"""Audit and summarize a bounded research run, without changing its evidence.

Run: uv run python -m scripts.research_summary results/followup-20261021/research
"""

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


def bootstrap_interval(values, seed=731):
    if len(values) < 2:
        return None
    values = np.asarray(values)
    rng = np.random.default_rng(seed)
    estimates = values[rng.integers(0, len(values), (2000, len(values)))].mean(axis=1)
    return np.quantile(estimates, [0.025, 0.975]).tolist()


def paired_cells(rows, baseline):
    cases = defaultdict(dict)
    for row in rows:
        if row.get("partition") == "primary" and row["method"] in ("bila", baseline):
            if row["method"] in cases[row["case"]]:
                raise ValueError("duplicate case/method")
            cases[row["case"]][row["method"]] = row
    cells = defaultdict(
        lambda: {"deltas": [], "noise": [], "bila_successes": 0, "baseline_successes": 0}
    )
    for pair in cases.values():
        anchor = next(iter(pair.values()))
        key = (anchor["scenario"], anchor["missing"])
        cell = cells[key]
        for method, count in (("bila", "bila_successes"), (baseline, "baseline_successes")):
            if pair.get(method, {}).get("status") == "success":
                cell[count] += 1
        if len(pair) != 2 or any(row["status"] != "success" for row in pair.values()):
            continue
        first, second = pair["bila"], pair[baseline]
        if not first.get("data_hash") or first["data_hash"] != second.get("data_hash"):
            raise ValueError("paired methods used different observations")
        cell["deltas"].append(first["metrics"]["energy"] - second["metrics"]["energy"])
        cell["noise"].append(
            first["metrics"].get("energy_mcse", 0) ** 2
            + second["metrics"].get("energy_mcse", 0) ** 2
        )
    result = []
    for (scenario, missing), cell in sorted(cells.items()):
        count = len(cell["deltas"])
        result.append(
            {
                "scenario": scenario,
                "missing": missing,
                "baseline": baseline,
                "pairs": count,
                "bila_successes": cell["bila_successes"],
                "baseline_successes": cell["baseline_successes"],
                "mean_delta": float(np.mean(cell["deltas"])) if count else None,
                "interval": bootstrap_interval(cell["deltas"]),
                "coarse_mcse_delta": float(np.sqrt(sum(cell["noise"])) / count) if count else None,
                "deltas": cell["deltas"],
            }
        )
    return result


def adaptation_contrast(cells):
    lookup = {(c["scenario"], c["missing"]): c["deltas"] for c in cells}
    keys = [(s, m) for s in ("scale", "shape") for m in (10, 30, 100)]
    if any(len(lookup.get(key, [])) < 2 for key in keys):
        return {
            "status": "unavailable",
            "reason": "At least one of the six declared cells lacks two jointly successful pairs.",
        }
    rng = np.random.default_rng(731)
    boot = np.zeros(2000)
    estimates = []
    for key in keys:
        values = np.asarray(lookup[key])
        estimates.append(values.mean())
        boot += values[rng.integers(0, len(values), (2000, len(values)))].mean(axis=1) / 6
    return {
        "status": "available",
        "estimate": float(np.mean(estimates)),
        "interval": np.quantile(boot, [0.025, 0.975]).tolist(),
        "pairs_per_cell": [len(lookup[key]) for key in keys],
    }


def audit_artifact(artifact, metrics):
    observed = np.array([np.nan if x is None else x for x in artifact["observed"]], dtype=float)
    truth, point = np.asarray(artifact["truth"]), np.asarray(artifact["point"])
    missing = np.flatnonzero(np.isnan(observed))
    if (
        not len(missing)
        or not np.all(np.diff(missing) == 1)
        or missing[0] == 0
        or missing[-1] == len(observed) - 1
        or len(truth) != len(missing)
        or len(point) != len(missing) + 2
        or not np.isfinite(truth).all()
        or not np.isfinite(point).all()
    ):
        raise ValueError("invalid saved gap or prediction")
    endpoints = observed[[missing[0] - 1, missing[-1] + 1]]
    tolerance = 1e-10 * max(1.0, float(np.abs(endpoints).max()))
    if np.max(np.abs(point[[0, -1]] - endpoints)) > tolerance:
        raise ValueError("prediction endpoint mismatch")
    error = point[1:-1] - truth
    rmse, mae = float(np.sqrt(np.mean(error**2))), float(np.abs(error).mean())
    if not np.isclose(rmse, metrics["rmse"], rtol=1e-10, atol=1e-12):
        raise ValueError("saved RMSE differs from independently recomputed value")
    if not np.isclose(mae, metrics["mae"], rtol=1e-10, atol=1e-12):
        raise ValueError("saved MAE differs from independently recomputed value")
    for coverage in (0.5, 0.8, 0.95):
        key = f"coverage_by_position_{coverage}"
        if key in metrics:
            flags = metrics[key]
            if len(flags) != len(truth) or not np.isclose(
                np.mean(flags), metrics[f"coverage_{coverage}"]
            ):
                raise ValueError("coverage count does not reconcile")
            if metrics[f"width_{coverage}"] < 0:
                raise ValueError("negative interval width")
    return {
        "missing": len(missing),
        "data_hash": hashlib.sha256(observed.tobytes()).hexdigest(),
        "rmse": rmse,
        "mae": mae,
    }


def summarize(manifest, rows, root):
    identifiers = [(r["case"], r["method"]) for r in rows]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("duplicate case/method records")
    catalog = {c["id"]: c for c in manifest["cases"]}
    orders = manifest["method_orders"]
    expected = {(case, method) for case, methods in orders.items() for method in methods}
    if (
        len(catalog) != len(manifest["cases"])
        or set(orders) != set(catalog)
        or len(expected) != manifest["planned"]
        or sum(map(len, orders.values())) != len(expected)
    ):
        raise ValueError("invalid declared application plan")
    recorded = set(identifiers)
    if recorded - expected:
        raise ValueError(f"unexpected applications: {sorted(recorded - expected)}")
    terminal = manifest["status"] != "running"
    if terminal and expected - recorded:
        raise ValueError(f"missing planned applications: {sorted(expected - recorded)}")
    root = root.resolve()
    successful_artifacts = 0
    reliability = defaultdict(list)
    for row in rows:
        case = catalog[row["case"]]
        for field in ("partition", "scenario", "missing", "replicate"):
            if row[field] != case[field]:
                raise ValueError("case metadata mismatch")
        if row.get("variant") != case.get("variant"):
            raise ValueError("prior sensitivity metadata mismatch")
        reliability[
            (
                row["partition"],
                row.get("variant", "default"),
                row["scenario"],
                row["missing"],
                row["method"],
            )
        ].append(row)
        if row["status"] != "success":
            continue
        path = (root / row["artifact"].replace("\\", "/")).resolve()
        if not path.is_relative_to(root) or path.suffix != ".json":
            raise ValueError("summary audit requires in-directory JSON artifacts")
        artifact = json.loads(path.read_text(encoding="utf-8"))
        audit = audit_artifact(artifact, row["metrics"])
        if audit["data_hash"] != row["data_hash"]:
            raise ValueError("saved observations differ from executed data hash")
        successful_artifacts += 1
    methods = []
    for (partition, variant, scenario, missing, method), group in sorted(reliability.items()):
        counts = Counter(r["status"] for r in group)
        good = [r for r in group if r["status"] == "success"]
        attempted = sum(r["status"] != "untested" for r in group)
        metrics = {}
        for metric in ("energy", "crps", "rmse", "mae", "coverage_0.95", "width_0.95"):
            values = [r["metrics"][metric] for r in good if metric in r.get("metrics", {})]
            metrics[metric] = float(np.mean(values)) if values else None
        methods.append(
            {
                "partition": partition,
                "variant": variant,
                "scenario": scenario,
                "missing": missing,
                "method": method,
                "attempted": attempted,
                "success": counts["success"],
                "unsuccessful": attempted - counts["success"],
                "untested": counts["untested"],
                "success_rate": counts["success"] / attempted if attempted else None,
                "status_counts": dict(counts),
                "successful_metrics": metrics,
                "median_elapsed_attempted": float(
                    np.median(
                        [
                            r["elapsed_seconds"]
                            for r in group
                            if r["status"] != "untested" and "elapsed_seconds" in r
                        ]
                    )
                )
                if any(r["status"] != "untested" and "elapsed_seconds" in r for r in group)
                else None,
                "peak_process_mib": max(
                    (r.get("diagnostics", {}).get("peak_process_mib", 0) for r in group), default=0
                ),
            }
        )
    baselines = sorted(
        {r["method"] for r in rows if r["method"] != "bila" and "energy" in r.get("metrics", {})}
    )
    pairs = {baseline: paired_cells(rows, baseline) for baseline in baselines}
    replication = []
    for scenario in ("gaussian", "skew", "scale", "shape"):
        for missing in (10, 30, 100):
            planned = [
                c
                for c in catalog.values()
                if c["partition"] == "primary"
                and c["scenario"] == scenario
                and c["missing"] == missing
            ]
            ids = {c["id"] for c in planned}
            attempted = {r["case"] for r in rows if r["case"] in ids and r["status"] != "untested"}
            pair = next(
                (
                    c
                    for c in pairs.get("pooled", [])
                    if c["scenario"] == scenario and c["missing"] == missing
                ),
                {},
            )
            replication.append(
                {
                    "scenario": scenario,
                    "missing": missing,
                    "target_series": len(planned),
                    "attempted_series": len(attempted),
                    "joint_bila_pooled_success": pair.get("pairs", 0),
                }
            )
    return {
        "status": manifest["status"],
        "planned": manifest["planned"],
        "records": len(rows),
        "statuses": dict(Counter(r["status"] for r in rows)),
        "source_signature": manifest["source_signature"],
        "observed_after_signature": manifest.get("observed_after_signature"),
        "analysis_source_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "audited_success_artifacts": successful_artifacts,
        "replication": replication,
        "reliability": methods,
        "paired_energy": pairs,
        "adaptation_contrast": adaptation_contrast(pairs.get("pooled", [])),
        "limitations": [
            *manifest.get("limitations", []),
            "Paired scores describe jointly successful cases; failure rates must accompany them.",
            "Bootstrap intervals resample independent series and are exploratory, with no multiplicity adjustment.",
            "Bootstrap intervals omit additional predictive Monte Carlo error; coarse score MCSE is reported separately.",
            "Without saved raw chains, energy/CRPS and empirical interval bounds cannot be independently recomputed from artifacts.",
            "Coverage summaries use successful outputs only and do not establish overall calibration when fits fail.",
        ],
    }


def number(value):
    if value is None:
        return "n/a"
    return f"{value:.5g}"


def write_outputs(root, summary, manifest):
    (root / "analysis.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8"
    )
    elapsed_label = "Last recorded elapsed" if manifest.get("elapsed_basis") else "Runtime"
    lines = [
        "# Research analysis and artifact audit",
        "",
        f"Stage status: **{summary['status']}**. {elapsed_label}: {manifest['elapsed_seconds'] / 60:.2f} minutes.",
        f"Recorded outcomes: {summary['statuses']}. Independently audited successful artifacts: {summary['audited_success_artifacts']}.",
        "",
        *[f"**Execution limitation:** {note}\n" for note in manifest.get("limitations", [])],
        f"Initial recorded source signature: `{summary['source_signature']}`.",
        *(
            [f"Observed after interruption: `{summary['observed_after_signature']}`."]
            if summary.get("observed_after_signature")
            else []
        ),
        "",
        "The experiment was capped; planned replication is a target, not achieved evidence.",
        "",
        "| Primary scenario | Missing values | Target series | Attempted series | Successful BiLA/pooled pairs |",
        "|---|---:|---:|---:|---:|",
    ]
    for cell in summary["replication"]:
        lines.append(
            f"| {cell['scenario']} | {cell['missing']} | {cell['target_series']} | {cell['attempted_series']} | {cell['joint_bila_pooled_success']} |"
        )
    lines += [
        "",
        "The predeclared six-cell adaptation contrast:",
        "",
        json.dumps(summary["adaptation_contrast"]),
        "",
        "Negative BiLA-minus-baseline energy favors BiLA on jointly successful pairs. Read reliability first.",
        "",
        "| Primary scenario | Missing | Baseline | Pairs | Mean energy difference | Exploratory 95% bootstrap interval | Coarse MCSE of mean difference |",
        "|---|---:|---|---:|---:|---|---:|",
    ]
    for baseline, cells in summary["paired_energy"].items():
        for cell in cells:
            lines.append(
                f"| {cell['scenario']} | {cell['missing']} | {baseline} | {cell['pairs']} | {number(cell['mean_delta'])} | {cell['interval']} | {number(cell['coarse_mcse_delta'])} |"
            )
    lines += [
        "",
        "| Partition | Prior variant | Scenario | Missing | Method | Attempted | Success | Unsuccessful | Untested | Successful-case 95% coverage | Median attempted seconds |",
        "|---|---|---|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for cell in summary["reliability"]:
        lines.append(
            f"| {cell['partition']} | {cell['variant']} | {cell['scenario']} | {cell['missing']} | {cell['method']} | {cell['attempted']} | {cell['success']} | {cell['unsuccessful']} | {cell['untested']} | {number(cell['successful_metrics']['coverage_0.95'])} | {number(cell['median_elapsed_attempted'])} |"
        )
    lines += ["", *[f"- {note}" for note in summary["limitations"]], ""]
    (root / "analysis.md").write_text("\n".join(lines), encoding="utf-8")
    for name, rows in (("replication", summary["replication"]),):
        with (root / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.run / "manifest.json").read_text(encoding="utf-8"))
    if manifest["stage"] != "research" or manifest["status"] == "running":
        parser.error("a terminal research manifest is required; running evidence is not final")
    recorded = json.loads((args.run / "results.json").read_text(encoding="utf-8"))
    if recorded["manifest"] != manifest:
        raise ValueError("results and manifest disagree")
    summary = summarize(manifest, recorded["results"], args.run)
    write_outputs(args.run, summary, manifest)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "audited_successes": summary["audited_success_artifacts"],
                "analysis": str(args.run / "analysis.md"),
            }
        )
    )


if __name__ == "__main__":
    main()
