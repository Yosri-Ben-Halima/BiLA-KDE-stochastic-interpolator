"""Run the read-only local issue monitor: uv run python -m scripts.issue_dashboard --open."""

import argparse
import json
import mimetypes
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from scripts.campaign_history import read_history
from scripts.issue_tracker import read_tracker

ASSETS = {
    "/": "index.html",
    "/styles.css": "styles.css",
    "/app.mjs": "app.mjs",
    "/model.mjs": "model.mjs",
}
DOCUMENTS = {
    "docs/usage/guide.md",
    "README.md",
    "docs/research/REFERENCES.md",
    "docs/validation/VERIFICATION.md",
    "docs/validation/FOLLOWUP_VALIDATION.md",
    "docs/validation/STEP1_VALIDATION.md",
    "docs/research/RESEARCH_CONCLUSIONS.md",
    "docs/research/EXECUTIVE_SUMMARY.md",
}


def _source(root, value):
    if any(part in value for part in ("\\", ":", "%", "\x00")):
        return None
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    target = (root / relative).resolve()
    if not target.is_relative_to(root) or target.suffix.lower() != ".md":
        return None
    allowed = relative.parts and (relative.parts[0] == ".scratch" or value in DOCUMENTS)
    return target if allowed and target.is_file() else None


def make_server(root: Path, port: int = 8765, research: Path | None = None) -> ThreadingHTTPServer:
    root = Path(root).resolve()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def respond(self, code, content, content_type="text/plain; charset=utf-8"):
            if isinstance(content, str):
                content = content.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
                "img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'",
            )
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            authority = self.headers.get("Host", "")
            allowed = {
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            }
            if authority not in allowed:
                self.respond(404, "Not found")
                return
            route = urlsplit(self.path)
            try:
                if route.path == "/api/state":
                    payload = read_tracker(root, research)
                    self.respond(
                        200, json.dumps(payload, allow_nan=False), "application/json; charset=utf-8"
                    )
                elif route.path == "/api/history":
                    self.respond(200, json.dumps(read_history(root), allow_nan=False),
                                 "application/json; charset=utf-8")
                elif route.path == "/api/source":
                    value = parse_qs(route.query).get("path", [""])[0]
                    target = _source(root, value)
                    if target:
                        self.respond(200, target.read_text(encoding="utf-8-sig"))
                    else:
                        self.respond(404, "Source is not available")
                elif route.path in ASSETS:
                    target = (root / "dashboard" / ASSETS[route.path]).resolve()
                    if not target.is_relative_to(root) or not target.is_file():
                        self.respond(404, "Asset is not available")
                        return
                    kind = (
                        "text/javascript"
                        if target.suffix == ".mjs"
                        else mimetypes.guess_type(target)[0]
                    )
                    self.respond(200, target.read_bytes(), f"{kind or 'text/plain'}; charset=utf-8")
                else:
                    self.respond(404, "Not found")
            except (OSError, UnicodeError, ValueError):
                self.respond(503, "Source temporarily unavailable; refresh to retry")

        def unsupported(self):
            self.respond(405, "This monitor is read-only")

        do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = unsupported

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--research", type=Path)
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    server = make_server(Path(__file__).resolve().parents[1], args.port, args.research)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"BiLA-KDE work dashboard: {url}", flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
