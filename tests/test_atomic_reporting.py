from pathlib import Path

import pytest

from benchmarks.runner import write_json


def test_json_publication_survives_a_transient_reader_lock(tmp_path, monkeypatch):
    target = tmp_path / "progress.json"
    target.write_text('{"old": true}')
    replace = Path.replace
    attempts, delays = [], []

    def locked_then_available(path, destination):
        attempts.append(path)
        if len(attempts) < 4:
            assert target.read_text() == '{"old": true}'
            raise PermissionError("reader temporarily holds target")
        return replace(path, destination)

    monkeypatch.setattr(Path, "replace", locked_then_available)
    monkeypatch.setattr("benchmarks.runner.time.sleep", delays.append)
    write_json(target, {"new": True})
    assert '"new": true' in target.read_text()
    assert 0 < sum(delays) <= 1


def test_persistent_publication_failure_is_bounded_and_preserves_evidence(tmp_path, monkeypatch):
    target = tmp_path / "progress.json"
    target.write_text('{"old": true}')
    attempts, delays = [], []

    def locked(path, destination):
        attempts.append(path)
        raise PermissionError("persistent lock")

    monkeypatch.setattr(Path, "replace", locked)
    monkeypatch.setattr("benchmarks.runner.time.sleep", delays.append)
    with pytest.raises(PermissionError):
        write_json(target, {"new": True})
    assert 1 < len(attempts) <= 10
    assert sum(delays) <= 1
    assert target.read_text() == '{"old": true}'
    assert '"new": true' in target.with_suffix(".tmp").read_text()
