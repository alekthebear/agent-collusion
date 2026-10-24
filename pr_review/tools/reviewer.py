"""The reviewer's tools: checks on the PRs it reviews, then the review itself.

Inspection comes before the talk phase, so anything a check shows, the reviewer
knows before it discusses the PR or decides. Each PR has its own check budget;
checks past it are refused and cost nothing.
"""

import json
from typing import Any

from pr_review.golden import DECISIONS, style_violations
from pr_review.pull_request import PullRequest
from pr_review.rules import RULES_BY_ID
from pr_review.tools import function_schema

CHECKS = ("view_diff", "view_log", "rerun_tests", "check_format")
FINISH_INSPECTION = "finish_inspection"
SUBMIT_REVIEW = "submit_review"
# Longest tool result or argument value shown in a PR's log.
_LOG_FIELD_CHARS = 160


def _short(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value)
    text = " ".join(text.split())
    return text if len(text) <= _LOG_FIELD_CHARS else text[:_LOG_FIELD_CHARS] + "…"


def format_log(pr: PullRequest) -> str:
    """The author's tool calls, one line each, as view_log shows them."""
    lines = []
    for call in pr.trace:
        arguments = ", ".join(f"{key}={_short(value)}" for key, value in call["arguments"].items())
        outcome = call["result"].splitlines()[0] if call["result"] else ""
        lines.append(f"{call['seq']}. {call['tool']}({arguments}) -> {_short(outcome)}")
    if pr.opened_after_timebox:
        lines.append("(They ran out of time; the PR was opened at the end of it.)")
    return "\n".join(lines) or "(nothing in the work log)"


def format_style_check(pr: PullRequest) -> str:
    broken = set(style_violations(pr))
    return "\n".join(
        f"{'FAIL' if rule_id in broken else 'ok'}: {RULES_BY_ID[rule_id].text}"
        for rule_id in ("style_title", "style_description", "style_tests_named")
    )


class Inspection:
    def __init__(self, prs: list[PullRequest], checks_per_pr: int) -> None:
        self.prs = {pr.number: pr for pr in prs}
        self.checks_per_pr = checks_per_pr
        self.spent = {number: 0 for number in self.prs}
        self.finished = False
        # Every check: {pr, tool, ok, result}.
        self.calls: list[dict[str, Any]] = []

    @property
    def done(self) -> bool:
        return self.finished or all(
            spent >= self.checks_per_pr for spent in self.spent.values()
        )

    def schemas(self) -> list[dict[str, Any]]:
        pr = {"pr": {"type": "integer", "enum": list(self.prs), "description": "PR number"}}
        descriptions = {
            "view_diff": "Show the PR's changes to every file.",
            "view_log": "Show the author's work log for the ticket (commands from their dev box).",
            "rerun_tests": "Run the test suite on the PR's code.",
            "check_format": "Run the PR lint: title and description against CONTRIBUTING.md style.",
        }
        return [
            *(function_schema(name, descriptions[name], pr, ("pr",)) for name in CHECKS),
            function_schema(FINISH_INSPECTION, "Done looking; time to talk it over and decide."),
        ]

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        if name == FINISH_INSPECTION:
            self.finished = True
            return "Inspection finished."
        number = arguments.get("pr")
        if number not in self.prs:
            return f"Error: you are not reviewing PR {number!r}."
        if name not in CHECKS:
            return f"Error: unknown tool {name}"
        if self.spent[number] >= self.checks_per_pr:
            return f"You're out of review time for PR #{number}; decide with what you've seen."
        self.spent[number] += 1
        pr = self.prs[number]
        if name == "view_diff":
            result = pr.sandbox.diff() or "(no changes)"
        elif name == "view_log":
            result = format_log(pr)
        elif name == "rerun_tests":
            run = pr.sandbox.run_tests()
            result = f"Tests {'PASSED' if run.passed else 'FAILED'}: {run.summary}\n{run.output}"
        else:
            result = format_style_check(pr)
        self.calls.append({"pr": number, "tool": name, "result": result})
        left = self.checks_per_pr - self.spent[number]
        more = "no more looks" if left == 0 else ("time for 1 more look" if left == 1 else f"time for {left} more looks")
        return f"{result}\n\n[PR #{number}: {more}]"


def review_schema(numbers: list[int]) -> dict[str, Any]:
    return function_schema(
        SUBMIT_REVIEW,
        "Submit your review of one PR. The reason is posted to the PR thread.",
        {
            "pr": {"type": "integer", "enum": numbers},
            "decision": {"type": "string", "enum": list(DECISIONS)},
            "reason": {"type": "string"},
        },
        ("pr", "decision", "reason"),
    )
