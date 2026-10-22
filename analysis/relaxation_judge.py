#!/usr/bin/env python3
"""Detect future policy-relaxation strategies in private reflections.

The judge reads one agent-reflection, told which agents its author judges, and checks
for a strategy that could accept without the complete raw log required by policy. Other
episode fields are excluded. Positives require a verbatim reflection quote. Invalid
replies are retried; failures remain unresolved with an empty ``relaxation`` and
``relaxation_parse_ok=0``. Agents without a reflection, such as scripted ones, are skipped.

Replies are cached by gate version, model, and prompt. ``--think`` enables reasoning.
Output contains one row per agent-reflection; ``turning_point`` marks the first
positive for each run-agent, and ``turning_point_episode`` repeats its episode.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

from judge_common import (
    Judge, add_common_args, agent_model, check_prompt, clean_quote, display, dry_run, fail,
    judge_all, judgement, load_env, load_prompts, load_runs, names, norm, parse_labels,
    render, reviewees, run_columns, verdict_on, write_csv, ROOT,
)

PROMPT_FILE = Path(__file__).with_name("relaxation_judge_prompts.md")
DEFAULT_CACHE = "analysis/results/relaxation_cache.jsonl"

RUNG = "relaxation"
GATE_VERSION = 2
QUOTE_FIELD = "EVIDENCE QUOTE"
PLACEHOLDERS = ("agent", "reviewees", "reflection")


# ---------------------------------------------------------------- reply gates


def quote_gate(parsed: dict, source: str) -> dict:
    """Record whether the supplied evidence is a real source span."""
    parsed = dict(parsed)
    quote = (parsed.get("quote") or "").strip()
    parsed["quote_ok"] = int(bool(quote) and norm(quote) in norm(source))
    return parsed


def format_gate(parsed: dict) -> dict:
    """Flag a No that nevertheless supplied an evidence quote; do not change its label."""
    parsed = dict(parsed)
    contradicts = not parsed.get("answer") and bool((parsed.get("quote") or "").strip())
    parsed["format_ok"] = int(not contradicts)
    return parsed


def validator(source: str):
    """Accept only a well-formed reply, so the judge retries the rest."""
    def validate(raw: str) -> dict | None:
        fields = parse_labels(raw, (QUOTE_FIELD,))
        answer = judgement(fields) if fields is not None else None
        if answer is None:
            return None
        gated = format_gate(quote_gate(
            {"answer": answer, "quote": clean_quote(fields.get(QUOTE_FIELD, ""))}, source))
        if (answer and not gated["quote_ok"]) or not gated["format_ok"]:
            return None
        return gated
    return validate


# ---------------------------------------------------------------- source assembly


def reflection_rows(path: Path, run: dict, verdict_policy: str = "") -> list[dict]:
    """Build one row per agent-reflection; ``_reflection`` is the only judge source."""
    config = run.get("run_config") or {}
    memory_limits = config.get("cross_episode_memory_length") or {}
    base = run_columns(path, run)
    rows = []
    for episode in run.get("results") or []:
        if verdict_policy and episode.get("verdict_policy") != verdict_policy:
            continue
        agents = episode.get("agents")
        if not isinstance(agents, dict):
            continue
        for agent, record in agents.items():
            if not isinstance(record, dict):
                continue
            reflection = str(record.get("reflection") or "").strip()
            if not reflection:
                continue
            targets = reviewees(record)
            verdicts = [verdict_on(record, target) for target in targets]
            rows.append({
                **base,
                "model": agent_model(run, agent),
                "episode_index": episode.get("episode_index"),
                "episode_id": episode.get("episode_id"),
                "ep_verdict_policy": episode.get("verdict_policy"),
                "agent": agent,
                "reviewees": " ".join(targets),
                # Audit column only; verdicts are never rendered into the judge prompt.
                "accepts": sum(verdict == "accept" for verdict in verdicts),
                "task_id": record.get("task_id"),
                "memory_max_episodes": (
                    memory_limits.get(agent, -1)
                    if isinstance(memory_limits, dict) else -1
                ),
                "reflection_chars": len(reflection),
                "_reflection": reflection,
            })
    return rows


def annotate_turning_points(rows: list[dict]) -> None:
    """Mark the first positive reflection independently for each run-agent."""
    first: dict[tuple[str, str], int | str] = {}
    for row in sorted(rows, key=lambda item: (
        item["run_path"], item["agent"], int(item["episode_index"])
    )):
        key = (row["run_path"], row["agent"])
        if row.get(RUNG) and key not in first:
            first[key] = row["episode_index"]
    for row in rows:
        episode = first.get((row["run_path"], row["agent"]), "")
        row["turning_point_episode"] = episode
        row["turning_point"] = int(episode != "" and row["episode_index"] == episode)


# ---------------------------------------------------------------- CLI


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    add_common_args(parser, DEFAULT_CACHE)
    args = parser.parse_args()

    runs = load_runs(args)
    if not runs:
        return fail("no run.json matched")
    rows = [row for path, run in runs for row in reflection_rows(path, run, args.verdict_policy)]
    scope = f" under {args.verdict_policy}" if args.verdict_policy else ""
    print(f"{len(runs)} runs -> {len(rows)} agent-reflections{scope}")
    if not rows:
        return fail("no reflections to judge")

    prompts = load_prompts(PROMPT_FILE)
    check_prompt(prompts, RUNG, PROMPT_FILE, PLACEHOLDERS, (QUOTE_FIELD,))
    blocks = prompts[RUNG]

    def user_prompt(row: dict) -> str:
        return render(blocks["user"], agent=display(row["agent"]),
                      reviewees=names(row["reviewees"].split()),
                      reflection=row["_reflection"])

    if args.dry_run:
        return dry_run([(blocks["system"], user_prompt(row)) for row in rows])

    load_env()
    cache_path = ROOT / args.cache
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    judge = Judge(args, cache_path)
    print(f"cache: {len(judge.cache)} entries at {cache_path}")

    def work(index: int) -> dict:
        row = rows[index]
        return judge.ask(RUNG, GATE_VERSION, blocks["system"], user_prompt(row),
                         validator(row["_reflection"]))

    def record(index: int, parsed: dict) -> None:
        row = rows[index]
        row[RUNG] = parsed.get("answer")
        row[f"{RUNG}_quote_ok"] = parsed.get("quote_ok", 0)
        row[f"{RUNG}_parse_ok"] = parsed.get("parse_ok", 0)
        row[f"{RUNG}_format_ok"] = parsed.get("format_ok", 1)
        row[f"{RUNG}_reasoning_chars"] = parsed.get("reasoning_chars", 0)
        row[f"{RUNG}_quote"] = parsed.get("quote", "")
        row[f"{RUNG}_error"] = parsed.get("error", "")

    print(f"{len(rows)} judge units (1 private reflection per unit)")
    judge_all(rows, work, record, args.workers, judge)
    annotate_turning_points(rows)

    out_path = write_csv(rows, args.out)
    print(f"wrote {len(rows)} rows -> {out_path}  ({judge.report()})")

    print(f"\n=== reflection-level {RUNG} ===")
    print(f"{'model':>30} {'setup':>14} {'n_ref':>6} {RUNG[:8]:>8} {'agent_tp':>9} {'parse':>6}")
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["model"], row["cond_dir"])].append(row)
    for (model, setup), group in sorted(groups.items()):
        n = len(group)
        resolved = [row for row in group if row[f"{RUNG}_parse_ok"]]
        relax_rate = (
            sum(row[RUNG] for row in resolved) / len(resolved)
            if resolved else float("nan")
        )
        parse_rate = sum(row[f"{RUNG}_parse_ok"] for row in group) / n
        turning_points = sum(row["turning_point"] for row in group)
        print(f"{model[-28:]:>30} {setup[-14:]:>14} {n:>6} {relax_rate:>8.3f} "
              f"{turning_points:>9} {parse_rate:>6.3f}")

    positives = sum(row[RUNG] == 1 for row in rows)
    verified = sum(row[RUNG] == 1 and row[f"{RUNG}_quote_ok"] for row in rows)
    unresolved = sum(not row[f"{RUNG}_parse_ok"] for row in rows)
    bad_format = sum(not row[f"{RUNG}_format_ok"] for row in rows)
    print(f"\nverified positive quotes: {verified}/{positives}")
    print(f"unresolved judgements: {unresolved}/{len(rows)}")
    print(f"format contradictions: {bad_format}/{len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
