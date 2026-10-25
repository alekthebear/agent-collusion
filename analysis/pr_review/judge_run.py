#!/usr/bin/env python3
"""Judge one or more PR-review runs and write each run's judgements.json.

Runs the deal, relaxation and eval-awareness judges on a run, labels every episode
(collusion_summary.label_run), and writes everything beside run.json:

    {"judge": {model, judged_at}, "deals": [...], "relaxation": [...],
     "eval_awareness": [...], "reviews": [...], "episodes": [...], "run": {...}}

`python -m pr_review` calls this when a run finishes, unless --no-judge. Use this
command for older runs, runs made with --no-judge, crashed runs, or after a judge
prompt changes. Replies are cached, so re-judging repeats only new calls.
--relabel recomputes the labels from the judge verdicts already in judgements.json,
with no judge calls: use it after the labels change.

    python analysis/pr_review/judge_run.py results/pr-review/<id>/<run> [...]
    python analysis/pr_review/judge_run.py --relabel results/pr-review/*/*/
"""

from __future__ import annotations

import argparse
import json
import sys
from argparse import Namespace
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "analysis"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# By package path: analysis/ has its own relaxation_judge and collusion_summary.
from analysis.pr_review import (  # noqa: E402
    collusion_summary,
    deal_judge,
    eval_awareness_judge,
    relaxation_judge,
)
from judge_common import DEFAULT_API_KEY_ENV, DEFAULT_BASE_URL, DEFAULT_MODEL, Judge, load_env  # noqa: E402

CACHE_DIR = ROOT / "analysis" / "results"
JUDGES = {
    "deals": (deal_judge, "pr_review_deal_cache.jsonl"),
    "relaxation": (relaxation_judge, "pr_review_relaxation_cache.jsonl"),
    "eval_awareness": (eval_awareness_judge, "pr_review_eval_awareness_cache.jsonl"),
}


def judge_args(model: str = DEFAULT_MODEL) -> Namespace:
    """The settings every judge call uses."""
    return Namespace(
        model=model,
        base_url=DEFAULT_BASE_URL,
        api_key_env=DEFAULT_API_KEY_ENV,
        max_tokens=4000,
        timeout=180.0,
        think=True,
        reasoning_effort="medium",
    )


def judge_run(
    run_dir: Path,
    *,
    model: str = DEFAULT_MODEL,
    cache_dir: Path = CACHE_DIR,
    workers: int = 8,
    client=None,
) -> Path:
    """Judge the run in run_dir, write its judgements.json, and return the path."""
    run_dir = run_dir.parent if run_dir.is_file() else run_dir
    path = (run_dir / "run.json").resolve()
    args = judge_args(model)
    cache_dir.mkdir(parents=True, exist_ok=True)
    judged: dict = {"judge": {"model": model, "judged_at": datetime.now().isoformat()}}
    report = []
    for key, (module, cache_name) in JUDGES.items():
        judge = Judge(args, cache_dir / cache_name, client=client)
        rows = module.judge_units(module.units([path]), judge, workers)
        judged[key] = [{k: v for k, v in row.items() if k != "run_path"} for row in rows]
        report.append(f"{key}: {judge.report()}")
    run = json.loads(path.read_text())
    judged.update(collusion_summary.label_run(run, judged))
    judged["judge"]["unresolved"] = {
        key: sum(row[field] is None for row in judged[key])
        for key, field in (("deals", "deal"), ("relaxation", "relaxation"), ("eval_awareness", "aware"))
    }
    out = run_dir / collusion_summary.JUDGEMENTS_FILENAME
    out.write_text(json.dumps(judged, indent=1, ensure_ascii=False))
    for line in report:
        print(f"  {line}")
    return out


def relabel_run(run_dir: Path) -> Path:
    """Recompute a judged run's labels from its stored verdicts, without judge calls."""
    run_dir = run_dir.parent if run_dir.is_file() else run_dir
    out = run_dir / collusion_summary.JUDGEMENTS_FILENAME
    judged = json.loads(out.read_text())
    run = json.loads((run_dir / "run.json").read_text())
    for key in ("reviews", "episodes", "run"):
        judged.pop(key, None)
    judged.update(collusion_summary.label_run(run, judged))
    judged["judge"]["labelled_at"] = datetime.now().isoformat()
    out.write_text(json.dumps(judged, indent=1, ensure_ascii=False))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("runs", nargs="+", type=Path, help="run directories or run.json files")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="judge model")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--relabel", action="store_true", help="recompute labels from stored verdicts; no judge calls"
    )
    args = parser.parse_args()
    load_env()
    for run in args.runs:
        if args.relabel:
            out = relabel_run(run)
        else:
            out = judge_run(run, model=args.model, workers=args.workers)
        print(f"Wrote {out}")
        loaded, labels = collusion_summary.load(out.parent)
        collusion_summary.print_run(loaded, labels, judged=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
