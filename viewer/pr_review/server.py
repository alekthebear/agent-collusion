"""Serve a local, read-only viewer for PR-review runs.

Usage: python -m viewer.pr_review [--results DIR] [--port 8766] [--no-browser]

Lists every run.json under results/pr-review and serves the selected run to
index.html, with the data from data.py. Nothing is written. For a single run as a
file that needs no server, see export.py.
"""

import argparse
import json
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pr_review.run import RESULTS_DIR
from viewer.pr_review.data import RUN_FILENAME, run_payload, summarize_run

VIEWER_DIR = Path(__file__).resolve().parent


class ViewerHandler(BaseHTTPRequestHandler):
    results_dir: Path

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: object, status: int = HTTPStatus.OK) -> None:
        self._send(status, json.dumps(payload).encode(), "application/json")

    def _run_path(self, relative: str) -> Path | None:
        """Resolve a requested run inside the results directory, or None."""
        candidate = (self.results_dir / relative).resolve()
        if candidate.name != RUN_FILENAME or not candidate.is_file():
            return None
        if not candidate.is_relative_to(self.results_dir):
            return None
        return candidate

    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            body = (VIEWER_DIR / "index.html").read_bytes()
            self._send(HTTPStatus.OK, body, "text/html; charset=utf-8")
        elif url.path == "/api/runs":
            runs = [
                summarize_run(path, self.results_dir)
                for path in self.results_dir.rglob(RUN_FILENAME)
            ]
            runs.sort(key=lambda run: run["mtime"], reverse=True)
            self._send_json({"results_dir": str(self.results_dir), "runs": runs})
        elif url.path == "/api/run":
            relative = parse_qs(url.query).get("path", [""])[0]
            path = self._run_path(relative)
            if path is None:
                self._send_json({"error": f"No run at {relative!r}"}, HTTPStatus.NOT_FOUND)
                return
            try:
                payload = run_payload(path)
            except (OSError, ValueError, KeyError) as exc:
                self._send_json({"error": f"{type(exc).__name__}: {exc}"}, HTTPStatus.CONFLICT)
                return
            self._send_json(payload)
        else:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", default=str(RESULTS_DIR))
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    results_dir = Path(args.results).expanduser().resolve()
    if not results_dir.is_dir():
        parser.error(f"results directory not found: {results_dir}")
    ViewerHandler.results_dir = results_dir

    server = ThreadingHTTPServer(("127.0.0.1", args.port), ViewerHandler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Serving PR-review runs from {results_dir}\nOpen {url}  (Ctrl-C to stop)", flush=True)
    if not args.no_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
