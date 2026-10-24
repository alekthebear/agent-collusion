"""Serve a local, read-only viewer for experiment runs.

Usage: python viewer/original/server.py [--results DIR] [--port 8765] [--no-browser]

Lists every run.json under the results directory and serves the selected file to
viewer/original/index.html. Nothing is written; only files under the results
directory are readable through the API.
"""

import argparse
import json
import threading
import webbrowser
from collections import defaultdict
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

VIEWER_DIR = Path(__file__).resolve().parent
REPO_ROOT = VIEWER_DIR.parents[1]
RUN_FILENAME = "run.json"
USAGE_JOURNAL_FILENAME = "llm_usage.jsonl"

# Run summaries keyed by path, reused while the file's mtime and size are unchanged.
_summary_cache: dict[Path, tuple[tuple[float, int], dict]] = {}
_cache_lock = threading.Lock()


def _accepts(verdict: str | None) -> bool:
    return verdict == "accept"


def _summarize_run(path: Path, results_dir: Path) -> dict:
    """Read the fields the run picker shows: models, progress, collusion, cost."""
    stat = path.stat()
    key = (stat.st_mtime, stat.st_size)
    with _cache_lock:
        cached = _summary_cache.get(path)
        if cached and cached[0] == key:
            return cached[1]

    summary: dict = {
        "path": path.relative_to(results_dir).as_posix(),
        "label": path.parent.name,
        "group": path.parent.parent.relative_to(results_dir).as_posix()
        if path.parent.parent != results_dir
        else "",
        "mtime": stat.st_mtime,
        "size": stat.st_size,
    }
    try:
        record = json.loads(path.read_text())
        config = record.get("run_config", {})
        results = record.get("results", [])
        summary.update(
            {
                # Runs from before agent groups existed are pairs.
                "group_kind": (config.get("agent_group") or {}).get("kind", "pair"),
                "agent_count": len(config.get("models", {})),
                "models": config.get("models", {}),
                "reasoning_efforts": config.get("reasoning_efforts", {}),
                "episodes_done": len(results),
                "episodes_total": config.get("pair_count"),
                "mutual_accepts": sum(
                    all(
                        _accepts(agent.get("verdict"))
                        for agent in episode.get("agents", {}).values()
                    )
                    for episode in results
                ),
                "cost_usd": (record.get("llm_usage_summary") or {}).get("cost_usd"),
            }
        )
    except (OSError, ValueError) as exc:
        # A run that is mid-write or malformed still appears, flagged.
        summary["error"] = f"{type(exc).__name__}: {exc}"

    with _cache_lock:
        _summary_cache[path] = (key, summary)
    return summary


def _invocation_start(invocation_id: str) -> datetime | None:
    """Invocation IDs begin with the launch time, e.g. 20261020T031552477865Z_f0848c."""
    try:
        return datetime.strptime(invocation_id.split("_")[0] + "+0000", "%Y%m%dT%H%M%S%fZ%z")
    except ValueError:
        return None


def _episode_timing(run_path: Path) -> dict:
    """Derive per-episode wall time from the usage journal beside run.json.

    Each record's recorded_at marks when a call finished. An episode runs from the end
    of the previous episode in the same invocation (or the invocation's launch) to its
    last call. The run total sums episodes, so idle gaps before a resume are excluded.
    """
    journal = run_path.parent / USAGE_JOURNAL_FILENAME
    if not journal.is_file():
        return {"available": False}
    by_invocation: dict[str, dict[int, datetime]] = defaultdict(dict)
    for line in journal.read_text().splitlines():
        try:
            record = json.loads(line)
            finished = datetime.fromisoformat(record["recorded_at"])
            episode = int(record["episode_index"])
        except (ValueError, KeyError, TypeError):
            continue
        ends = by_invocation[str(record.get("invocation_id", ""))]
        ends[episode] = max(ends.get(episode, finished), finished)

    episodes: dict[int, float] = {}
    # IDs start with the launch time, so sorting orders invocations; when a resume
    # re-runs an unfinished episode, the later invocation's timing wins.
    for invocation_id, ends in sorted(by_invocation.items()):
        previous_end = _invocation_start(invocation_id)
        for episode in sorted(ends):
            start = previous_end or min(ends.values())
            episodes[episode] = max((ends[episode] - start).total_seconds(), 0.0)
            previous_end = ends[episode]
    return {
        "available": True,
        "episode_seconds": {str(k): v for k, v in sorted(episodes.items())},
        "total_seconds": sum(episodes.values()),
        "invocations": len(by_invocation),
    }


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
                _summarize_run(path, self.results_dir)
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
            self._send(HTTPStatus.OK, path.read_bytes(), "application/json")
        elif url.path == "/api/timing":
            relative = parse_qs(url.query).get("path", [""])[0]
            path = self._run_path(relative)
            if path is None:
                self._send_json({"error": f"No run at {relative!r}"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json(_episode_timing(path))
        else:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", default=str(REPO_ROOT / "results"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    results_dir = Path(args.results).expanduser().resolve()
    if not results_dir.is_dir():
        parser.error(f"results directory not found: {results_dir}")
    ViewerHandler.results_dir = results_dir

    server = ThreadingHTTPServer(("127.0.0.1", args.port), ViewerHandler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Serving runs from {results_dir}\nOpen {url}  (Ctrl-C to stop)", flush=True)
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
