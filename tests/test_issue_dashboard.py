import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from scripts.issue_dashboard import make_server


@pytest.fixture
def server(tmp_path):
    folder = tmp_path / ".scratch/epic/issues"
    folder.mkdir(parents=True)
    (folder.parent / "map.md").write_text("# Epic\n\nStatus: open\n")
    (folder / "01-work.md").write_text(
        "# Work\n\nParent: [Epic](../map.md)\nStatus: open\n"
        "Assignee: unassigned\nBlocked by: none\n"
    )
    assets = tmp_path / "dashboard"
    assets.mkdir()
    (assets / "index.html").write_text("<!doctype html><title>Work</title>")
    instance = make_server(tmp_path, port=0)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield instance, f"http://127.0.0.1:{instance.server_port}"
    instance.shutdown()
    instance.server_close()
    thread.join(timeout=2)


def test_state_and_index_are_served_without_exposing_a_directory(server):
    _, url = server
    with urlopen(url + "/api/state") as response:
        state = json.load(response)
        assert state["counts"]["ready"] == 1
        assert response.headers["Cache-Control"] == "no-store"
    with urlopen(url + "/") as response:
        assert b"<title>Work</title>" in response.read()
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_indexed_markdown_is_available_as_plain_text(server):
    _, url = server
    with urlopen(url + "/api/source?path=.scratch/epic/issues/01-work.md") as response:
        assert response.headers.get_content_type() == "text/plain"
        assert response.read().startswith(b"# Work")


@pytest.mark.parametrize(
    "path",
    [
        "/.git/config",
        "/dashboard/",
        "/api/source?path=../README.md",
        "/api/source?path=%252e%252e%252fREADME.md",
        "/api/source?path=C:/Windows/win.ini",
        "/api/source?path=pyproject.toml",
        "/api/source?path=.scratch%5c..%5csecret.md",
    ],
)
def test_unsafe_or_unlisted_routes_are_rejected(server, path):
    _, url = server
    with pytest.raises(HTTPError) as exc:
        urlopen(url + path)
    assert exc.value.code == 404


def test_post_cannot_modify_issues(server):
    _, url = server
    with pytest.raises(HTTPError) as exc:
        urlopen(Request(url + "/api/state", data=b"change", method="POST"))
    assert exc.value.code == 405


def test_nonlocal_host_is_rejected(server):
    _, url = server
    with pytest.raises(HTTPError) as exc:
        urlopen(Request(url + "/api/state", headers={"Host": "example.com"}))
    assert exc.value.code == 404


def test_external_markdown_symlink_is_rejected(server, tmp_path):
    _, url = server
    outside = tmp_path.parent / (tmp_path.name + "-outside.md")
    outside.write_text("private external content")
    try:
        (tmp_path / ".scratch/external.md").symlink_to(outside)
    except OSError:
        pytest.skip("Creating a symlink is unavailable on this Windows account")
    with pytest.raises(HTTPError) as exc:
        urlopen(url + "/api/source?path=.scratch/external.md")
    assert exc.value.code == 404
