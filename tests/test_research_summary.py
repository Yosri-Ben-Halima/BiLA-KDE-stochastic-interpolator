import json

import pytest

from scripts.research_summary import adaptation_contrast, audit_artifact, paired_cells, summarize


def row(case, method, score, status="success", data_hash="same"):
    return {
        "case": case,
        "method": method,
        "scenario": "scale",
        "missing": 10,
        "partition": "primary",
        "status": status,
        "data_hash": data_hash,
        "metrics": {"energy": score, "energy_mcse": 0.1},
    }


def test_pairs_keep_failures_out_of_scores_but_do_not_invent_missing_pairs():
    rows = [
        row("a", "bila", 3),
        row("a", "pooled", 2),
        row("b", "bila", 1),
        row("b", "pooled", 3),
        row("c", "bila", 0, "time_limit"),
        row("c", "pooled", 7),
    ]
    cell = paired_cells(rows, "pooled")[0]
    assert cell["pairs"] == 2
    assert cell["mean_delta"] == -0.5
    assert cell["coarse_mcse_delta"] == pytest.approx(0.1)
    assert cell["bila_successes"] == 2
    assert cell["baseline_successes"] == 3


def test_mismatched_observed_series_cannot_be_paired():
    with pytest.raises(ValueError, match="observations"):
        paired_cells([row("a", "bila", 1), row("a", "pooled", 2, data_hash="other")], "pooled")


def test_partial_adaptation_grid_does_not_silently_reweight_remaining_cells():
    cells = [{"scenario": "scale", "missing": 10, "deltas": [1.0, 2.0]}]
    assert adaptation_contrast(cells)["status"] == "unavailable"


def test_complete_adaptation_grid_uses_equal_cell_weights():
    cells = [
        {"scenario": s, "missing": m, "deltas": [float(i), float(i)]}
        for i, (s, m) in enumerate((s, m) for s in ("scale", "shape") for m in (10, 30, 100))
    ]
    result = adaptation_contrast(cells)
    assert result["status"] == "available"
    assert result["estimate"] == 2.5
    assert result["interval"] == [2.5, 2.5]


def test_artifact_audit_independently_checks_point_error_and_observed_endpoints():
    artifact = {
        "observed": [0.0, 1.0, None, None, 5.0, 6.0],
        "truth": [2.0, 4.0],
        "point": [1.0, 2.5, 3.5, 5.0],
    }
    metrics = {"rmse": 0.5, "mae": 0.5}
    assert audit_artifact(artifact, metrics)["missing"] == 2
    broken = dict(artifact, point=[1.0, 2.5, 3.5, 5.1])
    with pytest.raises(ValueError, match="endpoint"):
        audit_artifact(broken, metrics)
    with pytest.raises(ValueError, match="RMSE"):
        audit_artifact(artifact, {"rmse": 1.0, "mae": 0.5})


def test_prior_sensitivity_variants_remain_separate(tmp_path):
    artifact = {
        "observed": [0.0, 1.0, None, None, 5.0, 6.0],
        "truth": [2.0, 4.0],
        "point": [1.0, 2.5, 3.5, 5.0],
    }
    metrics = {"rmse": 0.5, "mae": 0.5, "energy": 1.0, "energy_mcse": 0.1}
    digest = audit_artifact(artifact, metrics)["data_hash"]
    rows, cases = [], []
    for variant in ("variance", "mu"):
        case = {
            "id": variant,
            "partition": "sensitivity",
            "scenario": "gaussian",
            "missing": 2,
            "replicate": 0,
            "variant": variant,
        }
        cases.append(case)
        (tmp_path / f"{variant}.json").write_text(json.dumps(artifact))
        rows.append(
            {
                **{k: v for k, v in case.items() if k != "id"},
                "case": variant,
                "method": "bayesian_ar",
                "status": "success",
                "data_hash": digest,
                "metrics": metrics,
                "artifact": f"{variant}.json",
            }
        )
    manifest = {
        "cases": cases,
        "method_orders": {case["id"]: ["bayesian_ar"] for case in cases},
        "status": "complete",
        "planned": 2,
        "source_signature": "test",
    }
    result = summarize(manifest, rows, tmp_path)
    assert {r["variant"] for r in result["reliability"]} == {"variance", "mu"}


@pytest.mark.parametrize(
    "methods, message",
    [
        (["bila"], "missing planned applications"),
        (["bila", "unplanned_method"], "unexpected applications"),
        (["bila", "pooled", "unplanned_method"], "unexpected applications"),
    ],
)
def test_terminal_audit_checks_exact_planned_applications(tmp_path, methods, message):
    case = {
        "id": "x",
        "partition": "primary",
        "scenario": "scale",
        "missing": 10,
        "replicate": 0,
    }
    manifest = {
        "cases": [case],
        "method_orders": {"x": ["bila", "pooled"]},
        "status": "complete",
        "planned": 2,
        "source_signature": "test",
    }
    rows = [dict(row("x", method, 0, "untested"), replicate=0) for method in methods]
    with pytest.raises(ValueError, match=message):
        summarize(manifest, rows, tmp_path)


def test_recovered_run_preserves_its_execution_limitations_in_analysis(tmp_path):
    case = {"id": "x", "partition": "primary", "scenario": "scale", "missing": 10, "replicate": 0}
    manifest = {
        "cases": [case],
        "method_orders": {"x": ["bila"]},
        "status": "interrupted",
        "planned": 1,
        "source_signature": "initial",
        "observed_after_signature": "changed",
        "limitations": ["Interrupted during publication; no sampling resumed."],
    }
    result = summarize(manifest, [dict(row("x", "bila", 0, "untested"), replicate=0)], tmp_path)
    assert manifest["limitations"][0] in result["limitations"]
    assert result["observed_after_signature"] == "changed"
