"""Run the automated team for N workdays, resuming from the last saved day.

    python -m pipeline --run-dir results/pipeline/<id> --workdays 22 [--seed 1] [--new]

Keep the Mac awake with: caffeinate -i python -m pipeline ...
"""

import argparse
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

from pipeline.sim import RunConfig, World
from pr_review.llm import LLMResponder


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--workdays", type=int, required=True, help="total workdays the run should reach")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--model", default="deepseek/deepseek-flash")
    parser.add_argument("--new", action="store_true", help="create the run directory")
    parser.add_argument("--total-cost-limit", type=float, default=400.0)
    args = parser.parse_args()
    args.run_dir = args.run_dir.resolve()  # git worktree paths must be absolute
    config = RunConfig(model=args.model, seed=args.seed, workdays=args.workdays,
                       total_cost_limit=args.total_cost_limit)
    if args.new:
        World.create(args.run_dir, config)
    llm = SimpleNamespace(model=config.model, reasoning_effort=config.reasoning_effort,
                          temperature=config.temperature, max_output_tokens=config.max_output_tokens)
    responder = LLMResponder(llm, args.run_dir / "llm_usage.jsonl", uuid.uuid4().hex)
    usage = args.run_dir / "llm_usage.jsonl"

    def total() -> float:
        if not usage.exists():
            return 0.0
        return sum((json.loads(line).get("cost_usd") or 0) for line in usage.read_text().splitlines())

    w = World(args.run_dir, config, responder, total)
    w.restore()
    while w.day < args.workdays:
        log = w.run_day()
        merged = sum(1 for e in log.get("events", []) if e["kind"] == "review" and e.get("merged"))
        print(f"day {log['day']} {log['date']}: ${log['cost']} {log['seconds']}s, merged {merged}, "
              f"total ${total():.2f}", flush=True)
        if log["cost"] > config.day_cost_limit or total() > config.total_cost_limit:
            print("STOP: cost limit", flush=True)
            break


if __name__ == "__main__":
    main()
