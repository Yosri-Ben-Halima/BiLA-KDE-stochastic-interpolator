"""Read persistent campaign relationships and archived run evidence without writing them."""

import json
import time
from collections import Counter
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from scripts.issue_tracker import _activity, _json, _number


def _directory(root, value):
    if not isinstance(value, str) or any(c in value for c in ("\\", ":", "%", "\x00")):
        return None
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    target = (root / relative).resolve()
    return target if target.is_relative_to(root) and target.is_relative_to((root / "results").resolve()) else None


@lru_cache(maxsize=32)
def _outcomes(path, modified, size):
    # Cache only compact counts; large scientific result arrays are not retained.
    del modified, size
    def reject(value):
        raise ValueError(f"Invalid JSON constant {value}")
    payload = json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=reject)
    if not isinstance(payload, dict):
        raise TypeError("Outcome object required")
    rows = payload.get("results", payload.get("baseline", payload.get("candidate", [])))
    if not isinstance(rows, list):
        raise TypeError("Outcome list required")
    return dict(Counter(row["status"] for row in rows
                        if isinstance(row, dict) and isinstance(row.get("status"), str)))


def _record(root, folder, warnings):
    manifest = _json(folder / "manifest.json", warnings, root) or {}
    progress = {}
    if manifest.get("status") == "running" and (folder / "progress.json").exists():
        progress = _json(folder / "progress.json", warnings, root) or {}
    current = progress or manifest
    counts = {}
    results = folder / "results.json"
    if results.exists():
        try:
            if not results.resolve().is_relative_to((root / "results").resolve()):
                raise ValueError("Outcome source leaves results")
            info = results.stat()
            counts = _outcomes(str(results.resolve()), info.st_mtime_ns, info.st_size)
        except (OSError, ValueError, UnicodeError, TypeError):
            warnings.append(f"Unavailable outcomes: {folder.relative_to(root).as_posix()}")
    try:
        updated = datetime.fromtimestamp((folder / "manifest.json").stat().st_mtime, UTC).isoformat()
    except OSError:
        updated = None
    return {
        "source": folder.relative_to(root).as_posix(),
        "stage": manifest.get("stage", "unknown"),
        "status": manifest.get("status", "unavailable"),
        "purpose": manifest.get("purpose"),
        "verdict": manifest.get("verdict"),
        "attempted": _number(current.get("attempted")),
        "planned": _number(manifest.get("planned")),
        "elapsed_seconds": _number(current.get("elapsed_seconds")),
        "budget_seconds": _number(manifest.get("budget_seconds")),
        "source_signature": manifest.get("source_signature"),
        "config_hash": manifest.get("config_hash"),
        "updated_at": updated,
        "started_at": manifest.get("created_at"),
        "counts": counts,
        "activity": _activity(folder, root, warnings),
        "limitations": manifest.get("limitations", []),
    }


def read_history(root: Path, now=None):
    root = Path(root).resolve()
    now = time.time() if now is None else now
    warnings, records, covered = [], [], set()
    registry = root / "results/campaign-history.json"
    content = _json(registry, warnings, root) if registry.exists() else {}
    entries = (content or {}).get("campaigns", [])
    if not isinstance(entries, list):
        entries = []
        warnings.append("Invalid campaign history index")

    def add(entry):
        if not isinstance(entry, dict):
            warnings.append("Invalid campaign history entry")
            return
        folder = _directory(root, entry.get("source"))
        if folder is None:
            warnings.append("Campaign history source rejected")
            return
        local_warnings = []
        record = _record(root, folder, local_warnings)
        record.update(id=entry.get("id", record["source"]),
                      title=entry.get("title", folder.name.replace("-", " ")),
                      date=entry.get("date"), original_source=None, stages=[])
        covered.add(folder)
        original = _directory(root, entry.get("original_source"))
        if original:
            covered.add(original)
            record["original_source"] = original.relative_to(root).as_posix()
        stages = entry.get("stages", [])
        if not isinstance(stages, list):
            stages = []
            local_warnings.append("Invalid stage links")
        for stage in stages:
            child = _directory(root, stage.get("source")) if isinstance(stage, dict) else None
            if child is None:
                local_warnings.append("Campaign stage source rejected")
                continue
            covered.add(child)
            item = _record(root, child, local_warnings)
            item.update(label=stage.get("label", child.name), role=stage.get("role", "evidence"))
            record["stages"].append(item)
        additions = entry.get("additional_outcomes", [])
        if not isinstance(additions, list):
            additions = []
            local_warnings.append("Invalid additional outcome sources")
        aggregated = {folder}
        for location in additions:
            child = _directory(root, location)
            if child is None:
                local_warnings.append("Additional outcomes rejected")
                continue
            if child in aggregated:
                local_warnings.append("Duplicate additional outcomes omitted")
                continue
            aggregated.add(child)
            covered.add(child)
            extra = _record(root, child, local_warnings)
            counts = Counter(record["counts"])
            counts.update(extra["counts"])
            record["counts"] = dict(counts)
        record["warnings"] = local_warnings
        records.append(record)

    for entry in entries:
        add(entry)
    # Unregistered future runs remain visible without modifying the index.
    for path in sorted((root / "results").glob("**/manifest.json")):
        folder = path.parent.resolve()
        if folder in covered or any(folder.is_relative_to(source / "raw") for source in covered):
            continue
        if not folder.is_relative_to(root) or not folder.is_relative_to((root / "results").resolve()):
            warnings.append("Discovered campaign leaves results")
            continue
        add({"source": folder.relative_to(root).as_posix()})
    records.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return {"campaigns": records, "warnings": warnings,
            "recorded_at": datetime.fromtimestamp(now, UTC).isoformat(),
            "index_source": "results/campaign-history.json" if registry.exists() else None}
