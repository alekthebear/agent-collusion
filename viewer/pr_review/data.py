"""What the viewer shows for a run, shared by the server and the static export.

summarize_run gives the fields the runs list shows; run_payload gives a run joined
with what the page can't derive on its own: the metrics rows (knowing approvals),
the rules and which checks reveal each, the ticket texts, and the eval-awareness
pattern.
"""

import json
import threading
from collections import defaultdict
from pathlib import Path

from analysis.pr_review.metrics import AWARENESS, awareness_hits, decided, pr_rows
from pr_review.build_tasks import TASK_DIR
from pr_review.golden import APPROVE, REVEALED_BY
from pr_review.rules import RULES

RUN_FILENAME = "run.json"
USAGE_JOURNAL_FILENAME = "llm_usage.jsonl"

# Summaries keyed by path, reused while the file's mtime and size are unchanged.
_summary_cache: dict[Path, tuple[tuple[float, int], dict]] = {}
_cache_lock = threading.Lock()


def summarize_run(path: Path, results_dir: Path) -> dict:
    """The fields the run picker shows."""
    stat = path.stat()
    key = (stat.st_mtime, stat.st_size)
    with _cache_lock:
        cached = _summary_cache.get(path)
        if cached and cached[0] == key:
            return cached[1]
    summary: dict = {
        "path": path.relative_to(results_dir).as_posix(),
        "label": path.parent.name,
        "group": path.parent.parent.relative_to(results_dir).as_posix(),
        "mtime": stat.st_mtime,
    }
    try:
        run = json.loads(path.read_text())
        rows = pr_rows(run)
        config = run.get("config", {})
        # Reviewer measures count only reviews a model decided.
        reviews = decided(rows)
        false_approvals = [
            row for row in reviews if row["decision"] == APPROVE and row["golden"] != APPROVE
        ]
        summary.update(
            {
                "config_id": config.get("id"),
                "started_at": run.get("started_at"),
                "model": config.get("model"),
                "structure": config.get("structure"),
                "pressure": config.get("pressure"),
                "budget": config.get("budget"),
                "memory": config.get("memory"),
                "positive_control": config.get("positive_control"),
                "episodes_done": len(run.get("episodes", [])),
                "episodes_total": config.get("episodes"),
                "prs": len(rows),
                "approvals": sum(row["decision"] == APPROVE for row in rows),
                "golden_approvals": sum(row["golden"] == APPROVE for row in rows),
                "reviews": len(reviews),
                "correct_reviews": sum(row["decision"] == row["golden"] for row in reviews),
                "false_approvals": len(false_approvals),
                "knowing_false_approvals": sum(bool(row["knowing"]) for row in false_approvals),
                "false_rejections": sum(
                    row["decision"] != APPROVE and row["golden"] == APPROVE for row in reviews
                ),
                "rule_breaks": {
                    tier: sum(row["worst_tier"] == tier for row in rows)
                    for tier in ("never", "always", "style")
                },
                "dms": sum(
                    message["channel"] == "dm"
                    for episode in run.get("episodes", [])
                    for message in episode["messages"]
                ),
                "awareness_hits": len(awareness_hits(run)),
                "cost_usd": (run.get("llm_usage_summary") or {}).get("cost_usd"),
            }
        )
    except (OSError, ValueError, KeyError) as exc:
        # A run that is mid-write or malformed still appears, flagged.
        summary["error"] = f"{type(exc).__name__}: {exc}"
    with _cache_lock:
        _summary_cache[path] = (key, summary)
    return summary


def _tickets(run: dict) -> dict[str, dict]:
    """Each PR's task.json, keyed by task id, for the ticket text."""
    tickets = {}
    for episode in run["episodes"]:
        for pr in episode["prs"]:
            path = TASK_DIR / pr["task_id"] / "task.json"
            if path.is_file():
                tickets[pr["task_id"]] = json.loads(path.read_text())
    return tickets


def _date_messages(run: dict, journal: Path) -> None:
    """Give undated messages a time from the usage journal, for runs from before
    messages carried one. Each agent makes one talk call per round, so a message in
    round k comes from its sender's k-th talk call; a posted review comes from the
    reviewer's last verdict call. The time is when that call returned, just before the
    message was posted; at_source marks it as derived.
    """
    if not journal.is_file():
        return
    calls: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for line in journal.read_text().splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if record.get("response_status", "accepted") == "accepted" and record.get("recorded_at"):
            key = (record.get("episode_id"), record.get("actor"), record.get("phase"))
            calls[key].append(record["recorded_at"])
    for episode in run["episodes"]:
        episode_id = f"episode_{episode['episode']}"
        for message in episode["messages"]:
            if message.get("at"):
                continue
            if message["round"] == "review":
                times = calls.get((episode_id, message["sender"], "verdict"), [])
                at = max(times) if times else None
            else:
                times = sorted(calls.get((episode_id, message["sender"], "talk"), []))
                at = times[message["round"] - 1] if len(times) >= message["round"] else None
            if at:
                message["at"] = at
                message["at_source"] = "model call"


def run_payload(path: Path) -> dict:
    run = json.loads(path.read_text())
    _date_messages(run, path.parent / USAGE_JOURNAL_FILENAME)
    return {
        "run": run,
        "rows": pr_rows(run),
        "rules": [{"id": rule.rule_id, "tier": rule.tier, "text": rule.text} for rule in RULES],
        "revealed_by": REVEALED_BY,
        "tickets": _tickets(run),
        "awareness": AWARENESS.pattern,
    }
