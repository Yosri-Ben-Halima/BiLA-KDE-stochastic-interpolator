"""History remains usable when saved evidence is partial, changing, or unsafe."""

import json
import os
from pathlib import Path

import pytest

from scripts.campaign_history import read_history


def saved_run(root, manifest=None):
    folder = root / "results" / "saved"
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(
        json.dumps(manifest or {"stage": "smoke", "status": "validated"}),
        encoding="utf-8",
    )
    return folder


def registry(root, entries):
    (root / "results" / "campaign-history.json").write_text(
        json.dumps({"campaigns": entries}), encoding="utf-8"
    )


def test_missing_registry_discovers_runs_without_creating_an_index(tmp_path):
    saved_run(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}

    history = read_history(tmp_path)

    assert history["index_source"] is None
    assert len(history["campaigns"]) == 1
    assert history["campaigns"][0]["status"] == "validated"
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("content", ["{", "[]", '{"campaigns":{}}', '{"campaigns":[null]}'])
def test_invalid_registry_reports_warning_and_keeps_discovered_evidence(tmp_path, content):
    saved_run(tmp_path)
    index = tmp_path / "results" / "campaign-history.json"
    index.write_text(content, encoding="utf-8")

    history = read_history(tmp_path)

    assert len(history["campaigns"]) == 1
    assert history["campaigns"][0]["status"] == "validated"
    assert history["warnings"]
    assert index.read_text(encoding="utf-8") == content


@pytest.mark.parametrize("content", [None, "{", "[]"])
def test_registered_missing_or_invalid_manifest_stays_visible_as_unavailable(tmp_path, content):
    folder = saved_run(tmp_path)
    manifest = folder / "manifest.json"
    if content is None:
        manifest.unlink()
    else:
        manifest.write_text(content, encoding="utf-8")
    registry(tmp_path, [{"id": "remembered", "title": "Remembered run", "source": "results/saved"}])

    history = read_history(tmp_path)

    assert len(history["campaigns"]) == 1
    row = history["campaigns"][0]
    assert row["id"] == "remembered"
    assert row["title"] == "Remembered run"
    assert row["status"] == "unavailable"
    assert row["counts"] == {}
    assert row["warnings"]
    assert row["attempted"] is None


@pytest.mark.parametrize("content", [None, "{", "[]", '{"results":{}}', '{"results":[NaN]}'])
def test_missing_or_invalid_outcomes_do_not_hide_manifest_status(tmp_path, content):
    folder = saved_run(tmp_path)
    if content is not None:
        (folder / "results.json").write_text(content, encoding="utf-8")

    row = read_history(tmp_path)["campaigns"][0]

    assert row["status"] == "validated"
    assert row["counts"] == {}
    if content is not None:
        assert row["warnings"]


@pytest.mark.parametrize("field", ["results", "baseline", "candidate"])
def test_supported_outcome_archives_report_recorded_outcomes(tmp_path, field):
    folder = saved_run(tmp_path)
    (folder / "results.json").write_text(json.dumps({field: [
        {"status": "success"}, {"status": "success"}, {"status": "time_limit"},
        {"status": "untested"}, {}, {"status": None}, "incomplete row",
    ]}), encoding="utf-8")

    row = read_history(tmp_path)["campaigns"][0]

    assert row["counts"] == {"success": 2, "time_limit": 1, "untested": 1}
    assert row["warnings"] == []


@pytest.mark.parametrize("status, attempted, elapsed", [("running", 2, 15), ("validated", 1, 5)])
def test_progress_updates_only_live_counts_without_replacing_manifest_provenance(
    tmp_path, status, attempted, elapsed
):
    folder = saved_run(tmp_path, {
        "stage": "smoke", "status": status, "attempted": 1, "elapsed_seconds": 5,
        "planned": 3, "budget_seconds": 60, "source_signature": "frozen-source",
    })
    (folder / "progress.json").write_text(json.dumps({
        "attempted": 2, "elapsed_seconds": 15, "planned": 999,
        "budget_seconds": 999, "source_signature": "different-source", "status": "failed",
    }), encoding="utf-8")

    row = read_history(tmp_path)["campaigns"][0]

    assert (row["attempted"], row["elapsed_seconds"]) == (attempted, elapsed)
    assert row["status"] == status
    assert row["planned"] == 3
    assert row["budget_seconds"] == 60
    assert row["source_signature"] == "frozen-source"


def test_invalid_running_progress_falls_back_to_manifest_and_reports_warning(tmp_path):
    folder = saved_run(tmp_path, {"status": "running", "attempted": 1, "elapsed_seconds": 5})
    (folder / "progress.json").write_text("{", encoding="utf-8")

    row = read_history(tmp_path)["campaigns"][0]

    assert (row["attempted"], row["elapsed_seconds"]) == (1, 5)
    assert row["warnings"]


def test_changed_outcomes_are_visible_on_the_next_read_even_at_the_same_file_size(tmp_path):
    folder = saved_run(tmp_path)
    results = folder / "results.json"
    results.write_text('{"results":[{"status":"success"}]}', encoding="utf-8")
    assert read_history(tmp_path)["campaigns"][0]["counts"] == {"success": 1}
    previous = results.stat()
    results.write_text('{"results":[{"status":"failure"}]}', encoding="utf-8")
    # Set a definite new timestamp; filesystem clock resolution must not make this flaky.
    os.utime(results, ns=(previous.st_atime_ns, previous.st_mtime_ns + 2_000_000_000))
    assert results.stat().st_size == previous.st_size

    assert read_history(tmp_path)["campaigns"][0]["counts"] == {"failure": 1}


@pytest.mark.parametrize("filename", ["manifest.json", "results.json", "narrative.json"])
def test_external_evidence_is_rejected_without_exposing_its_contents(tmp_path, monkeypatch, filename):
    root = tmp_path / "workspace"
    folder = saved_run(root)
    secret = "private-external-evidence"
    contents = {
        "manifest.json": {"status": secret, "purpose": secret},
        "results.json": {"results": [{"status": secret}]},
        "narrative.json": {"entries": [{
            "id": "private", "at": "2026-10-21T12:00:00+00:00", "title": secret, "detail": secret,
        }]},
    }
    source = folder / filename
    source.write_text(json.dumps(contents[filename]), encoding="utf-8")
    external = tmp_path / "outside.json"
    external.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    actual_resolve = Path.resolve

    def redirected_resolve(path, *args, **kwargs):
        # Model a file symlink deterministically, including on Windows without symlink privileges.
        resolved = actual_resolve(path, *args, **kwargs)
        return external if resolved == source else resolved

    monkeypatch.setattr(Path, "resolve", redirected_resolve)

    history = read_history(root)

    assert len(history["campaigns"]) == 1
    assert history["campaigns"][0]["warnings"]
    assert secret not in json.dumps(history)
