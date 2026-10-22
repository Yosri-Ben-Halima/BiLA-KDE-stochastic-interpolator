import argparse
import hashlib
import json
import time
import tomllib
from pathlib import Path

import numpy as np

from bilakde.config import SamplingConfig
from bilakde.errors import BridgeError
from bilakde.resources import run_guarded

from .methods import METHODS, evaluate
from .oracles import oracle_cases, reference_case, validate_bayesian
from .scenarios import STRESS, generate, primary_cases, seed_for

ROOT = Path(__file__).resolve().parents[1]


def source_signature():
    digest = hashlib.sha256()
    files = sorted((ROOT / "src/bilakde").glob("*.py")) + sorted((ROOT / "benchmarks").glob("*.py"))
    for path in files:
        digest.update(str(path.relative_to(ROOT)).replace("\\", "/").encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def reserve_case(remaining, method_count, per_method):
    return remaining >= method_count * per_method + 5


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, (np.integer, np.bool_)):
        return value.item()
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    return value


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(clean(value), indent=2, allow_nan=False), encoding="utf-8")
    # Windows readers can briefly deny rename/delete sharing. Keep the old
    # complete JSON visible, retry briefly, and retain the temp file on failure.
    delays = (0, 0.01, 0.02, 0.04, 0.08, 0.16, 0.25, 0.25)
    for attempt, delay in enumerate(delays):
        if delay:
            time.sleep(delay)
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == len(delays) - 1:
                raise


def write_artifact(stem, arrays, save_chains):
    """Keep compact JSON summaries when retained binary chains are not requested."""
    path = stem.parent / (stem.name + (".npz" if save_chains else ".json"))
    if save_chains:
        np.savez_compressed(path, **arrays)
    else:
        write_json(path, arrays)
    return path


def interval(values, rng):
    values = np.asarray(values)
    if len(values) < 2:
        return None
    means = values[rng.integers(0, len(values), (2000, len(values)))].mean(axis=1)
    return np.quantile(means, [0.025, 0.975]).tolist()


def report(out, manifest, rows):
    write_json(out / "results.json", {"manifest": manifest, "results": rows})
    lines = [
        "# BiLA-KDE research evidence",
        "",
        f"Stage: {manifest['stage']}; status: {manifest['status']}.",
        f"Attempted coverage: {manifest['attempted']}/{manifest['planned']} ({100 * manifest['attempted'] / max(1, manifest['planned']):.1f}%).",
        f"Elapsed: {manifest['elapsed_seconds']:.1f} seconds. Unsuccessful and untested cases remain in the results.",
        "",
        "| Method | Success | Unsuccessful | Untested | Mean successful path energy |",
        "|---|---:|---:|---:|---:|",
    ]
    for method in METHODS:
        group = [r for r in rows if r["method"] == method]
        good = [r for r in group if r["status"] == "success"]
        energy = [r["metrics"]["energy"] for r in good if "energy" in r.get("metrics", {})]
        mean = f"{np.mean(energy):.5g}" if energy else "n/a"
        lines.append(
            f"| {method} | {len(good)} | {sum(r['status'] not in ('success', 'untested') for r in group)} | {sum(r['status'] == 'untested' for r in group)} | {mean} |"
        )
    lines += [
        "",
        "Mean successful scores alone are not a fair overall ranking: methods can succeed on different cases.",
        "Results are exploratory, conditional on the declared fitted models and success subset. Bayesian parameter uncertainty differs from plug-in KDE uncertainty.",
        "",
    ]
    paired = []
    by_case = {}
    for row in rows:
        if row["status"] == "success" and row["method"] in ("bila", "pooled"):
            by_case.setdefault(row["case"], {})[row["method"]] = row
    cells = {}
    for name, pair in by_case.items():
        if len(pair) == 2 and pair["bila"].get("partition") == "primary":
            delta = pair["bila"]["metrics"]["energy"] - pair["pooled"]["metrics"]["energy"]
            key = (pair["bila"]["scenario"], pair["bila"]["missing"])
            cells.setdefault(key, []).append(delta)
            paired.append({"case": name, "delta": delta})
    lines += [
        "| Primary cell | Jointly successful pairs | BiLA-minus-pooled energy | 95% exploratory interval |",
        "|---|---:|---:|---|",
    ]
    rng = np.random.default_rng(731)
    for key, values in sorted(cells.items()):
        lines.append(f"| {key} | {len(values)} | {np.mean(values):.5g} | {interval(values, rng)} |")
    adaptation = [cells.get((s, m), []) for s in ("scale", "shape") for m in (10, 30, 100)]
    if all(len(v) >= 2 for v in adaptation):
        boot = np.zeros(2000)
        for v in adaptation:
            a = np.asarray(v)
            boot += a[rng.integers(0, len(a), (2000, len(a)))].mean(axis=1) / 6
        estimate = float(np.mean([np.mean(v) for v in adaptation]))
        lines += [
            "",
            f"Predeclared equal-cell adaptation contrast: {estimate:.5g}; 95% stratified interval {np.quantile(boot, [0.025, 0.975]).tolist()}.",
            "This is a jointly successful subset and must be read with method reliability and incomplete target counts.",
        ]
    else:
        lines += [
            "",
            "Primary adaptation aggregate unavailable: at least one cell lacks two jointly successful pairs.",
        ]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(out / "paired_differences.json", paired)


def research_cases(config):
    result = list(primary_cases(config["replicates"]))
    # Sensitivity is deliberately after the complete primary grid.
    for variant in ("variance", "mu"):
        for base in primary_cases(min(5, config["replicates"])):
            result.append(
                dict(
                    base,
                    id=base["id"] + "-sensitivity-" + variant,
                    partition="sensitivity",
                    variant=variant,
                )
            )
    for replicate in range(config["stress_replicates"]):
        for scenario in STRESS:
            result.append(
                {
                    "id": f"{scenario}-gap30-r{replicate}",
                    "scenario": scenario,
                    "missing": 30,
                    "replicate": replicate,
                    "partition": "stress",
                }
            )
    return result


def case_methods(case):
    if case.get("variant") == "variance":
        return ("bayesian_local_level", "gaussian_bridge", "bayesian_ar", "plugin_ar")
    if case.get("variant") == "mu":
        return ("bayesian_ar", "plugin_ar")
    shift = (case["replicate"] + case["missing"] + sum(case["scenario"].encode())) % len(METHODS)
    return METHODS[shift:] + METHODS[:shift]


def main(started=None):
    started = time.perf_counter() if started is None else started
    parser = argparse.ArgumentParser(description="Bounded, paired BiLA-KDE research stages")
    parser.add_argument("--stage", choices=["smoke", "research"], required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "benchmarks/default.toml")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--smoke", type=Path, help="Validated smoke directory required for research"
    )
    parser.add_argument(
        "--budget-seconds", type=float, help="May lower, never increase, the stage cap"
    )
    args = parser.parse_args()
    config = tomllib.loads(args.config.read_text(encoding="utf-8"))
    if config["window_size"] != 100:
        parser.error("the declared primary protocol requires window_size=100")
    canonical_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    signature = source_signature()
    cap = config[args.stage + "_seconds"]
    if args.budget_seconds is not None:
        if not 0 < args.budget_seconds <= cap:
            parser.error("budget override must be positive and within stage cap")
        cap = args.budget_seconds
    deadline = started + cap
    if args.stage == "research":
        if args.smoke is None:
            parser.error("--smoke is required for research")
        smoke = json.loads((args.smoke / "manifest.json").read_text(encoding="utf-8"))
        if (
            smoke.get("status") != "validated"
            or smoke["source_signature"] != signature
            or smoke["config_hash"] != canonical_hash
        ):
            parser.error(
                "research requires validated smoke evidence for the exact source/configuration"
            )
    out = args.output or ROOT / "results" / f"{args.stage}-{time.time_ns()}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "artifacts").mkdir()
    if args.stage == "smoke":
        cases = [
            {
                "id": f"smoke-{s}-gap{m}",
                "scenario": s,
                "missing": m,
                "replicate": 0,
                "partition": "smoke",
            }
            for s, m in [("gaussian", 10), ("ar_gaussian", 30), ("shape", 30)]
        ]
    else:
        cases = research_cases(config)
    oracle_plan = (
        [("bayesian-reference", None)]
        + [
            (
                f"oracle-{c['kind']}-T{c['T']}-z{c['z']}",
                dict(c, n_samples=config.get("reference_samples", 16000)),
            )
            for c in oracle_cases()
        ]
        if args.stage == "smoke"
        else []
    )
    planned = len(oracle_plan) + sum(len(case_methods(c)) for c in cases)
    manifest = {
        "schema_version": 1,
        "stage": args.stage,
        "status": "running",
        "config": config,
        "config_hash": canonical_hash,
        "source_signature": signature,
        "budget_seconds": cap,
        "planned": planned,
        "attempted": 0,
        "elapsed_seconds": time.perf_counter() - started,
        "cases": cases,
        "reference_cases": [c[0] for c in oracle_plan],
        "method_orders": {c["id"]: case_methods(c) for c in cases},
        "parent_smoke": str(args.smoke) if args.smoke else None,
    }
    write_json(out / "manifest.json", manifest)
    rows = []

    def add(row):
        rows.append(clean(row))
        with (out / "cases.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(clean(row), allow_nan=False) + "\n")
        manifest.update(
            attempted=sum(r["status"] != "untested" for r in rows),
            elapsed_seconds=time.perf_counter() - started,
        )
        write_json(
            out / "progress.json",
            {
                "attempted": manifest["attempted"],
                "planned": planned,
                "percent": 100 * manifest["attempted"] / planned,
                "elapsed_seconds": manifest["elapsed_seconds"],
                "last_case": row["case"],
                "last_method": row["method"],
                "last_status": row["status"],
            },
        )

    for name, case in oracle_plan:
        if deadline - time.perf_counter() < config["per_method_seconds"] + 5:
            add({"case": name, "method": "reference", "status": "untested"})
            continue
        settings = SamplingConfig(
            time_limit_seconds=config["per_method_seconds"],
            memory_limit_bytes=config["memory_limit_bytes"],
        )
        function = validate_bayesian if case is None else reference_case
        arguments = (config["seed"], settings) if case is None else (case, config["seed"], settings)
        try:
            result = run_guarded(function, arguments, settings)
            add({"case": name, "method": "reference", "status": "success", **result})
        except BridgeError as exc:
            add(
                {
                    "case": name,
                    "method": "reference",
                    "status": exc.status,
                    "reason": exc.reason,
                    "diagnostics": exc.diagnostics,
                }
            )
        report(out, manifest, rows)
    for case in cases:
        methods = case_methods(case)
        if not reserve_case(
            deadline - time.perf_counter(), len(methods), config["per_method_seconds"]
        ):
            for method in methods:
                add(
                    {
                        "case": case["id"],
                        "method": method,
                        "status": "untested",
                        **{k: v for k, v in case.items() if k != "id"},
                    }
                )
            continue
        # Sensitivity reuses exactly the same generated observations as primary.
        data_case = dict(case, partition="primary") if case["partition"] == "sensitivity" else case
        series, truth = generate(data_case, config["seed"])
        data_hash = hashlib.sha256(series.tobytes()).hexdigest()
        prior = (
            (3.0, 2.0, 0.01)
            if case.get("variant") == "variance"
            else (2.0, 1.0, 0.001 if case.get("variant") == "mu" else 0.01)
        )
        for method in methods:
            settings = SamplingConfig(
                time_limit_seconds=config["per_method_seconds"],
                memory_limit_bytes=config["memory_limit_bytes"],
            )
            begin = time.perf_counter()
            header = {
                "case": case["id"],
                "method": method,
                **{k: v for k, v in case.items() if k != "id"},
                "data_hash": data_hash,
                "seed": seed_for(config["seed"], case["id"], method),
            }
            try:
                result = run_guarded(
                    evaluate,
                    (method, series, truth, header["seed"], config["n_samples"], settings, prior),
                    settings,
                )
                stem = out / "artifacts" / f"{case['id']}-{method}"
                arrays = {"point": result.pop("point"), "truth": truth, "observed": series}
                chains = result.pop("chains")
                if config["save_chains"] and chains is not None:
                    arrays["chains"] = chains
                artifact = write_artifact(stem, arrays, config["save_chains"])
                add(
                    dict(
                        header,
                        status="success",
                        elapsed_seconds=time.perf_counter() - begin,
                        artifact=str(artifact.relative_to(out)),
                        **result,
                    )
                )
            except BridgeError as exc:
                add(
                    dict(
                        header,
                        status=exc.status,
                        reason=exc.reason,
                        diagnostics=exc.diagnostics,
                        elapsed_seconds=time.perf_counter() - begin,
                    )
                )
        report(out, manifest, rows)
        print(
            f"{manifest['attempted']}/{planned} ({100 * manifest['attempted'] / planned:.1f}%) {case['id']}",
            flush=True,
        )
    good = {r["method"] for r in rows if r["status"] == "success"}
    references = [r for r in rows if r["method"] == "reference"]
    valid = (
        set(METHODS) <= good
        and len(references) == len(oracle_plan)
        and all(r["status"] == "success" for r in references)
    )
    manifest["status"] = (
        ("validated" if valid else "incomplete")
        if args.stage == "smoke"
        else ("complete" if all(r["status"] != "untested" for r in rows) else "incomplete")
    )
    manifest.update(
        elapsed_seconds=time.perf_counter() - started,
        validated_methods=sorted(good - {"reference"}),
    )
    write_json(out / "manifest.json", manifest)
    report(out, manifest, rows)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "output": str(out),
                "attempted": manifest["attempted"],
                "planned": planned,
                "elapsed_seconds": manifest["elapsed_seconds"],
            }
        ),
        flush=True,
    )
    return 0
