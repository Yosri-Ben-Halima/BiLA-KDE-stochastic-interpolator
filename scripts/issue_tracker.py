"""Read local wayfinder issues without maintaining a second status database."""

import json
import math
import re
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

STATUSES = ("ready", "in_progress", "blocked", "resolved", "attention")
CLOSED = {"resolved", "closed", "done"}
LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def _counts(rows):
    counter = Counter(row["status"] for row in rows)
    return {status: counter[status] for status in STATUSES}


def _read(path, root):
    warnings = []
    text = ""
    try:
        if not path.resolve().is_relative_to(root):
            raise ValueError("source leaves the repository")
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError, ValueError) as exc:
        warnings.append(f"Cannot read source: {type(exc).__name__}")
    heading = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = heading[1].strip() if heading else path.stem
    if not heading:
        warnings.append("Missing issue title")
    # Metadata precedes the first second-level section; body text cannot change it.
    prefix = re.split(r"^##\s", text, maxsplit=1, flags=re.MULTILINE)[0]
    metadata = {
        key.strip().lower(): value.strip()
        for key, value in re.findall(r"^([A-Za-z][A-Za-z ]*):\s*(.*)$", prefix, re.MULTILINE)
    }
    return title, metadata, text, warnings


def _json_number(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Nonfinite JSON number")
    return number


def _json(path, warnings, root):
    try:
        if not path.resolve().is_relative_to(root):
            warnings.append(f"{path.name} leaves the repository")
            return None
        result = json.loads(
            path.read_text(encoding="utf-8"), parse_float=_json_number, parse_constant=_json_number
        )
        if not isinstance(result, dict):
            raise TypeError("expected an object")
        return result
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        warnings.append(f"Unavailable {path.name}: {type(exc).__name__}")
        return None


def _number(value):
    return value if type(value) in (int, float) and 0 <= value < float("inf") else None


def _stamp(path, root, warnings):
    try:
        if not path.resolve().is_relative_to(root):
            warnings.append(f"{path.name} timestamp leaves the repository")
            return None
        return path.stat().st_mtime
    except OSError:
        warnings.append(f"Unavailable {path.name} timestamp")
        return None


def _activity(research, root, warnings):
    narrative = research / "narrative.json"
    path = narrative if narrative.exists() else research / "activity.json"
    if not path.exists():
        return []
    payload = _json(path, warnings, root)
    if payload is None:
        return []
    entries = payload.get("entries")
    if not isinstance(entries, list):
        warnings.append(f"Invalid {path.name} entries")
        return []
    valid, seen = [], set()
    for entry in entries:
        try:
            if not isinstance(entry, dict) or any(
                not isinstance(entry.get(key), str) or not entry[key].strip()
                for key in ("id", "at", "title", "detail")
            ):
                raise ValueError("missing activity fields")
            stamp = datetime.fromisoformat(entry["at"])
            if stamp.tzinfo is None or entry["id"] in seen:
                raise ValueError("ambiguous activity identity or time")
            fields = ("testing", "why", "observed", "meaning", "next")
            if any(key in entry and not isinstance(entry[key], str) for key in fields):
                raise ValueError("invalid narrative field")
            stamp = stamp.astimezone(UTC)
            seen.add(entry["id"])
            valid.append(
                (
                    stamp,
                    {
                        key: stamp.isoformat() if key == "at" else entry[key]
                        for key in ("id", "at", "title", "detail", *fields)
                        if key in entry
                    },
                )
            )
        except (ValueError, TypeError, OverflowError):
            warnings.append(f"Invalid {path.name} entry omitted")
    return [entry for _, entry in sorted(valid, key=lambda item: item[0])]


def _campaign(root, research, now):
    if research is None:
        candidates = []
        discovery_warnings = []
        for path in (root / "results").glob("**/manifest.json"):
            stamp = _stamp(path, root, discovery_warnings)
            if stamp is None:
                return {"status": "unavailable", "warnings": discovery_warnings}
            candidates.append((stamp, path))
        for _, path in sorted(candidates, key=lambda item: item[0], reverse=True):
            data = _json(path, discovery_warnings, root)
            if data is None:
                discovery_warnings.append(
                    "Cannot select the current campaign from an unreadable manifest"
                )
                return {"status": "unavailable", "warnings": discovery_warnings}
            if data.get("stage") == "research":
                research = path.parent
                break
        if research is None:
            return None
    research = Path(research)
    if not research.is_absolute():
        research = root / research
    research = research.resolve()
    if not research.is_relative_to(root):
        return {"warnings": ["Campaign directory leaves the repository"], "status": "unavailable"}
    warnings = []
    manifest = _json(research / "manifest.json", warnings, root) or {}
    progress = _json(research / "progress.json", warnings, root) or {}
    terminal = manifest.get("status") not in (None, "running")
    actual = manifest if terminal else progress
    attempted = _number(actual.get("attempted"))
    planned = _number(manifest.get("planned"))
    elapsed = _number(actual.get("elapsed_seconds"))
    cap = _number(manifest.get("budget_seconds"))
    stamps = [
        stamp
        for name in ("manifest.json", "progress.json")
        if (stamp := _stamp(research / name, root, warnings)) is not None
    ]
    age = max(0, now - max(stamps)) if stamps else None
    return {
        "source": research.relative_to(root).as_posix(),
        "status": manifest.get("status", "unavailable"),
        "attempted": attempted,
        "planned": planned,
        "elapsed_seconds": elapsed,
        "budget_seconds": cap,
        "budget_percent": 100 * elapsed / cap if elapsed is not None and cap else None,
        "application_percent": 100 * attempted / planned
        if attempted is not None and planned
        else None,
        "last_case": progress.get("last_case"),
        "last_method": progress.get("last_method"),
        "last_status": progress.get("last_status"),
        "age_seconds": age,
        "stale": bool(not terminal and (age is None or age > 120)),
        "activity": _activity(research, root, warnings),
        "warnings": warnings,
    }


def read_tracker(root: Path, research: Path | None = None, now: float | None = None) -> dict:
    root = Path(root).resolve()
    now = time.time() if now is None else now
    epics, issues, warnings = [], [], []
    if not (root / ".scratch").is_dir():
        warnings.append("Scratch tracker directory is unavailable")
    for source in sorted((root / ".scratch").glob("*/map.md")):
        title, metadata, _, problems = _read(source, root)
        epic_id = source.relative_to(root).as_posix()
        epic = {
            "id": epic_id,
            "title": title,
            "source": epic_id,
            "recorded_status": metadata.get("status", "unknown"),
            "warnings": problems,
            "summary": None,
        }
        summary = source.parent / "summary.md"
        if summary.exists():
            _, _, body, summary_problems = _read(summary, root)
            epic["warnings"].extend(summary_problems)
            if not summary_problems:
                epic["summary"] = {
                    "source": summary.relative_to(root).as_posix(),
                    "body": body,
                }
        epics.append(epic)
        for path in sorted((source.parent / "issues").glob("*.md")):
            name, meta, body, problems = _read(path, root)
            for required in ("parent", "status", "assignee", "blocked by"):
                if not meta.get(required):
                    problems.append(f"Missing {required} metadata")
            parent = LINK.fullmatch(meta.get("parent", ""))
            if not parent or (path.parent / parent[2]).resolve() != source.resolve():
                problems.append("Invalid parent reference for this epic")
            issue_id = path.relative_to(root).as_posix()
            issues.append(
                {
                    "id": issue_id,
                    "title": name,
                    "epic_id": epic_id,
                    "raw_status": meta.get("status", "unknown").lower(),
                    "assignee": meta.get("assignee", "unassigned"),
                    "type": meta.get("type", "task"),
                    "mode": meta.get(
                        "mode", "HITL" if meta.get("type") in ("grilling", "prototype") else "AFK"
                    ),
                    "blockers": [],
                    "warnings": problems,
                    "body": body,
                    "source": issue_id,
                    "_blocking": meta.get("blocked by", "none"),
                }
            )
    lookup = {row["id"]: row for row in issues}
    for row in issues:
        declaration = row.pop("_blocking")
        if declaration.lower() in ("none", "—", "-", "n/a"):
            continue
        links = LINK.findall(declaration)
        targets = []
        for _, target in links:
            path = (root / row["source"]).parent / target.split("#")[0]
            resolved = path.resolve()
            targets.append(
                resolved.relative_to(root).as_posix()
                if resolved.is_relative_to(root)
                else "outside repository"
            )
        # Named links and legacy numbers may coexist. Every residual token must
        # resolve or warn, rather than disappearing when any link is present.
        for number in filter(str.strip, LINK.sub("", declaration).split(",")):
            matches = [
                other["id"]
                for other in issues
                if other["epic_id"] == row["epic_id"]
                and Path(other["id"]).name.startswith(number.strip() + "-")
            ]
            targets.extend(matches if len(matches) == 1 else [f"unknown {number.strip()}"])
        for target in targets:
            if target not in lookup:
                row["warnings"].append(f"Missing blocker: {target}")
            elif target not in row["blockers"]:
                row["blockers"].append(target)
    visited, active, cyclic = set(), [], set()

    def visit(identity):
        if identity in active:
            cyclic.update(active[active.index(identity) :])
        elif identity not in visited:
            active.append(identity)
            for blocker in lookup[identity]["blockers"]:
                visit(blocker)
            active.pop()
            visited.add(identity)

    for identity in lookup:
        visit(identity)
    for row in issues:
        if row["id"] in cyclic:
            row["warnings"].append("Dependency cycle")
        raw = row["raw_status"]
        if raw in CLOSED:
            row["status"] = "resolved"
        elif raw != "open" or row["warnings"]:
            if raw != "open":
                row["warnings"].append(f"Unrecognized status: {raw}")
            row["status"] = "attention"
        elif any(lookup[b]["raw_status"] not in CLOSED for b in row["blockers"]):
            row["status"] = "blocked"
        else:
            assigned = row["assignee"].lower() not in ("unassigned", "none", "—", "-")
            row["status"] = "in_progress" if assigned else "ready"
    for epic in epics:
        children = [row for row in issues if row["epic_id"] == epic["id"]]
        epic.update(
            total=len(children),
            resolved=sum(r["status"] == "resolved" for r in children),
            counts=_counts(children),
        )
        warnings.extend(epic["warnings"])
    return {
        "epics": epics,
        "issues": issues,
        "counts": _counts(issues),
        "campaign": _campaign(root, research, now),
        "warnings": warnings,
        "generated_at": datetime.fromtimestamp(now, UTC).isoformat(),
    }
