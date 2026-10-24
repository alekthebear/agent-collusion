"""Write a run's viewer as one static HTML file, beside its run.json.

Usage: python -m viewer.pr_review.export RUN [RUN ...]

RUN is a run directory or its run.json. The file is index.html with the run's data
embedded, so it opens straight from disk or can be shared, with no server. It holds
only that run. `python -m pr_review` writes one when a run finishes.
"""

import argparse
import json
from pathlib import Path

from viewer.pr_review.data import RUN_FILENAME, run_payload, summarize_run

VIEWER_DIR = Path(__file__).resolve().parent
EXPORT_FILENAME = "viewer.html"
# Where index.html takes the embedded data.
STATIC_MARKER = "<!-- static-data -->"


def export_run(run: Path) -> Path:
    """Write viewer.html for one run and return its path."""
    path = run / RUN_FILENAME if run.is_dir() else run
    run_dir = path.parent
    data = {
        # Relative to the config folder's parent, so the page shows the config as its group.
        "summary": summarize_run(path.resolve(), run_dir.resolve().parent.parent),
        "payload": run_payload(path),
    }
    # "</" can't appear inside a script element; "<\/" is the same string in JSON.
    embedded = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = (VIEWER_DIR / "index.html").read_text()
    if STATIC_MARKER not in page:
        raise ValueError(f"index.html has no {STATIC_MARKER} marker")
    page = page.replace(STATIC_MARKER, f"<script>window.STATIC = {embedded};</script>", 1)
    out = run_dir / EXPORT_FILENAME
    out.write_text(page)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("runs", nargs="+", type=Path)
    args = parser.parse_args()
    for run in args.runs:
        print(f"Wrote {export_run(run)}")


if __name__ == "__main__":
    main()
