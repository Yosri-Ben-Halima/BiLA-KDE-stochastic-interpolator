import json
import os
from pathlib import Path

import pytest

from scripts.issue_tracker import read_tracker


def issue(root, name, status="open", owner="unassigned", blockers="none", extra=""):
    folder = root / ".scratch" / "example"
    (folder / "issues").mkdir(parents=True, exist_ok=True)
    (folder / "map.md").write_text("# Example epic\n\nLabel: wayfinder:map\nStatus: open\n")
    path = folder / "issues" / f"{name}.md"
    path.write_text(
        f"# {name}\n\nParent: [Example](../map.md)\nLabel: wayfinder:task\n"
        f"Type: task\nStatus: {status}\nAssignee: {owner}\nBlocked by: {blockers}\n"
        f"\n## Question\n\n{extra or 'Work to inspect.'}\n",
        encoding="utf-8",
    )
    return path.relative_to(root).as_posix()


def by_title(state):
    return {row["title"]: row for row in state["issues"]}


def test_statuses_and_epic_counts_are_derived_from_sources(tmp_path):
    issue(tmp_path, "01-done", status="resolved")
    issue(tmp_path, "02-claimed", owner="Codex", blockers="01")
    issue(tmp_path, "03-blocked", blockers="[Claimed](02-claimed.md)")
    issue(tmp_path, "04-ready", blockers="[Done](01-done.md)")
    state = read_tracker(tmp_path)
    rows = by_title(state)
    assert [rows[name]["status"] for name in sorted(rows)] == [
        "resolved",
        "in_progress",
        "blocked",
        "ready",
    ]
    assert state["counts"] == {
        "ready": 1,
        "in_progress": 1,
        "blocked": 1,
        "resolved": 1,
        "attention": 0,
    }
    assert state["epics"][0]["resolved"] == 1
    assert state["epics"][0]["total"] == 4
    assert rows["03-blocked"]["blockers"] == [rows["02-claimed"]["id"]]


def test_missing_blockers_and_cycles_need_attention(tmp_path):
    issue(tmp_path, "01-missing", blockers="99")
    issue(tmp_path, "02-cycle", blockers="03")
    issue(tmp_path, "03-cycle", blockers="02")
    state = read_tracker(tmp_path)
    assert all(row["status"] == "attention" for row in state["issues"])
    assert all(row["warnings"] for row in state["issues"])


def test_missing_required_metadata_does_not_look_ready(tmp_path):
    source = issue(tmp_path, "01-bad")
    path = tmp_path / source
    path.write_text("# Incomplete issue\n\nStatus: open\n")
    state = read_tracker(tmp_path)
    assert state["issues"][0]["status"] == "attention"


def test_duplicate_titles_keep_distinct_source_identities(tmp_path):
    first = issue(tmp_path, "01-first")
    second = issue(tmp_path, "02-second")
    for path in (first, second):
        actual = tmp_path / path
        text = actual.read_text().splitlines()
        text[0] = "# Same title"
        actual.write_text("\n".join(text))
    rows = read_tracker(tmp_path)["issues"]
    assert len({row["id"] for row in rows}) == 2
    assert {row["title"] for row in rows} == {"Same title"}


def test_empty_epic_has_no_manufactured_progress(tmp_path):
    folder = tmp_path / ".scratch/empty"
    folder.mkdir(parents=True)
    (folder / "map.md").write_text("# Empty\n\nStatus: open\n")
    epic = read_tracker(tmp_path)["epics"][0]
    assert (epic["total"], epic["resolved"]) == (0, 0)


def test_missing_tracker_directory_has_a_source_warning(tmp_path):
    state = read_tracker(tmp_path)
    assert state["issues"] == []
    assert state["warnings"]


def test_resolved_import_stays_resolved_with_followup_warning(tmp_path):
    issue(tmp_path, "01-history", status="resolved", blockers="99")
    row = read_tracker(tmp_path)["issues"][0]
    assert row["status"] == "resolved"
    assert row["warnings"]


def campaign(root, progress):
    path = root / "results/campaign"
    path.mkdir(parents=True)
    (path / "manifest.json").write_text(
        json.dumps(
            {
                "stage": "research",
                "status": "running",
                "planned": 500,
                "budget_seconds": 14400,
            }
        )
    )
    (path / "progress.json").write_text(json.dumps(progress))
    return path


def test_campaign_budget_attempts_and_staleness_are_separate(tmp_path):
    path = campaign(tmp_path, {"attempted": 100, "elapsed_seconds": 3600})
    now = max(p.stat().st_mtime for p in path.iterdir()) + 121
    data = read_tracker(tmp_path, research=path, now=now)["campaign"]
    assert data["budget_percent"] == 25
    assert data["application_percent"] == 20
    assert data["stale"] is True
    assert data["status"] == "running"


def test_malformed_progress_is_reported_without_fake_zero_counts(tmp_path):
    path = campaign(tmp_path, {})
    (path / "progress.json").write_text('{"attempted":')
    data = read_tracker(tmp_path, research=path)["campaign"]
    assert data["attempted"] is None
    assert data["elapsed_seconds"] is None
    assert data["warnings"]


@pytest.mark.parametrize("status", ["incomplete", "complete"])
def test_terminal_campaign_uses_terminal_manifest(tmp_path, status):
    path = campaign(tmp_path, {"attempted": 5, "elapsed_seconds": 120})
    manifest = json.loads((path / "manifest.json").read_text())
    manifest.update(status=status, attempted=100, elapsed_seconds=14401)
    (path / "manifest.json").write_text(json.dumps(manifest))
    data = read_tracker(tmp_path, research=path)["campaign"]
    assert data["status"] == status
    assert data["attempted"] == 100
    assert data["budget_percent"] > 100


def test_mixed_blocker_formats_do_not_drop_unknown_dependencies(tmp_path):
    issue(tmp_path, "01-done", status="resolved")
    issue(tmp_path, "02-waiting", blockers="[Done](01-done.md), 99")
    row = by_title(read_tracker(tmp_path))["02-waiting"]
    assert row["status"] == "attention"
    assert any("99" in warning for warning in row["warnings"])


def test_malformed_newest_manifest_does_not_substitute_an_old_complete_run(tmp_path):
    old = campaign(tmp_path, {})
    manifest = old / "manifest.json"
    data = json.loads(manifest.read_text())
    data["status"] = "complete"
    manifest.write_text(json.dumps(data))
    os.utime(manifest, (100, 100))
    current = tmp_path / "results/current"
    current.mkdir()
    (current / "manifest.json").write_text('{"stage": "research",')
    os.utime(current / "manifest.json", (200, 200))
    result = read_tracker(tmp_path)["campaign"]
    assert result["status"] == "unavailable"
    assert result["warnings"]


@pytest.mark.parametrize("filename", ["manifest.json", "progress.json", "activity.json"])
def test_campaign_leaf_files_are_confined_before_reading(tmp_path, monkeypatch, filename):
    folder = campaign(tmp_path, {"attempted": 100, "elapsed_seconds": 3600})
    aliased = folder / filename
    if filename == "activity.json":
        aliased.write_text('{"entries": []}')
    original_resolve = Path.resolve
    original_read = Path.read_text
    external = tmp_path.parent / "outside-campaign.json"
    seen = []

    def resolve(path, *args, **kwargs):
        return external if path == aliased else original_resolve(path, *args, **kwargs)

    def read(path, *args, **kwargs):
        seen.append(path)
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(Path, "read_text", read)
    result = read_tracker(tmp_path, research=folder)["campaign"]
    assert aliased not in seen
    assert result["warnings"]


def test_campaign_optional_activity_and_timestamp_order(tmp_path):
    folder = campaign(tmp_path, {})
    result = read_tracker(tmp_path, research=folder)["campaign"]
    assert result["activity"] == []
    assert not result["warnings"]
    entries = [
        {
            "id": "later",
            "at": "2026-10-21T12:00:00Z",
            "title": "Audit",
            "detail": "Checks passed",
            "next": "Wait",
        },
        {
            "id": "earlier",
            "at": "2026-10-21T11:00:00+00:00",
            "title": "Run",
            "detail": "Comparing methods",
        },
    ]
    (folder / "activity.json").write_text(json.dumps({"entries": entries}))
    result = read_tracker(tmp_path, research=folder)["campaign"]
    assert [entry["id"] for entry in result["activity"]] == ["earlier", "later"]
    assert result["activity"][1]["next"] == "Wait"


@pytest.mark.parametrize(
    "payload",
    [
        {"entries": "invalid"},
        {"entries": [{"at": "yesterday"}]},
        {
            "entries": [
                {
                    "id": "overflow",
                    "at": "0001-01-01T00:00:00+01:00",
                    "title": "Invalid UTC",
                    "detail": "Outside datetime range",
                }
            ]
        },
        {
            "entries": [
                {"id": "x", "at": "2026-10-21T12:00:00", "title": "Naive", "detail": "No zone"}
            ]
        },
    ],
)
def test_campaign_bad_activity_warns_without_breaking_board(tmp_path, payload):
    issue(tmp_path, "01-ready")
    folder = campaign(tmp_path, {})
    (folder / "activity.json").write_text(json.dumps(payload))
    state = read_tracker(tmp_path, research=folder)
    assert state["counts"]["ready"] == 1
    assert state["campaign"]["activity"] == []
    assert state["campaign"]["warnings"]


@pytest.mark.parametrize("stamp", ["20261021T120000Z", "2026-10-21T12:00:10+00:00:10"])
def test_activity_times_are_normalized_for_browser_dates(tmp_path, stamp):
    folder = campaign(tmp_path, {})
    entry = {"id": "update", "at": stamp, "title": "Run", "detail": "Working"}
    (folder / "activity.json").write_text(json.dumps({"entries": [entry]}))
    result = read_tracker(tmp_path, research=folder)["campaign"]
    assert result["activity"][0]["at"] == "2026-10-21T12:00:00+00:00"


def test_invalid_parent_is_not_a_ready_issue(tmp_path):
    source = issue(tmp_path, "01-parent")
    path = tmp_path / source
    path.write_text(
        path.read_text().replace("Parent: [Example](../map.md)", "Parent: not-a-parent")
    )
    row = read_tracker(tmp_path)["issues"][0]
    assert row["status"] == "attention"
    assert any("parent" in warning.lower() for warning in row["warnings"])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonstandard_json_numbers_do_not_break_the_issue_snapshot(tmp_path, value):
    issue(tmp_path, "01-ready")
    path = campaign(tmp_path, {"last_case": value, "attempted": 100})
    result = read_tracker(tmp_path, research=path)
    assert result["counts"]["ready"] == 1
    json.dumps(result, allow_nan=False)
    assert result["campaign"]["warnings"]
