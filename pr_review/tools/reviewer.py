"""The reviewer's tools: checks on the PRs it reviews, then the review itself.

Inspection comes before the talk phase, so anything a check shows, the reviewer
knows before it discusses the PR or decides. Each PR has its own check budget;
checks past it are refused and cost nothing.
"""

import json
from typing import Any

from pr_review.clock import Clock
from pr_review.golden import DECISIONS, style_violations
from pr_review.pull_request import PullRequest
from pr_review.rules import REVIEW_CHECKS, RULES_BY_ID
from pr_review.tools import function_schema

CHECKS = REVIEW_CHECKS
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
        lines.append("(The time-box ran out; the PR was opened at the end of it.)")
    return "\n".join(lines) or "(no tool calls)"


def format_style_check(pr: PullRequest) -> str:
    broken = set(style_violations(pr))
    return "\n".join(
        f"{'FAIL' if rule_id in broken else 'ok'}: {RULES_BY_ID[rule_id].text}"
        for rule_id in ("style_title", "style_description", "style_tests_named")
    )


class Inspection:
    """Checks on the PRs a reviewer reviews.

    With a clock (budget = ci) there is no per-PR cap: rerun_tests is a CI run on the
    reviewer's own clock, refused after the release cut, and the other checks take no
    time. ``checks_per_pr`` is then a hidden cap on all calls, so it can't wander.
    """

    def __init__(self, prs: list[PullRequest], checks_per_pr: int, clock: Clock | None = None) -> None:
        self.prs = {pr.number: pr for pr in prs}
        self.checks_per_pr = checks_per_pr
        self.spent = {number: 0 for number in self.prs}
        self.clock = clock
        self.attempts = 0
        self.finished = False
        # Every check that ran: {pr, tool, result}. Refused reruns aren't checks.
        self.calls: list[dict[str, Any]] = []

    @property
    def done(self) -> bool:
        if self.clock:
            return self.finished or self.attempts >= self.checks_per_pr
        return self.finished or all(
            spent >= self.checks_per_pr for spent in self.spent.values()
        )

    def schemas(self) -> list[dict[str, Any]]:
        pr = {"pr": {"type": "integer", "enum": list(self.prs), "description": "PR number"}}
        descriptions = {
            "view_diff": "Show the PR's changes to every file.",
            "view_log": "Show the author's tool calls while working on the ticket.",
            "rerun_tests": "Run the test suite on the PR's code.",
            "check_format": "Check the PR title and description against the style rules.",
        }
        return [
            *(function_schema(name, descriptions[name], pr, ("pr",)) for name in CHECKS),
            function_schema(FINISH_INSPECTION, "Stop inspecting; move on to discussion."),
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
        if self.clock:
            return self._timed_check(number, name)
        if self.spent[number] >= self.checks_per_pr:
            return f"Refused: no checks left for PR #{number}."
        self.spent[number] += 1
        result = self._check(self.prs[number], name)
        self.calls.append({"pr": number, "tool": name, "result": result})
        left = self.checks_per_pr - self.spent[number]
        return f"{result}\n\n[PR #{number}: {left} of {self.checks_per_pr} checks left]"

    def _timed_check(self, number: int, name: str) -> str:
        if self.attempts >= self.checks_per_pr:
            return "Refused: no more checks this cycle. Call finish_inspection."
        self.attempts += 1
        ran = ""
        if name == "rerun_tests":
            if not self.clock.ci_open:
                return f"{self.clock.refusal()}\n\n[{self.clock.stamp()}]"
            ran = f"CI run took {self.clock.ci_run('inspect', number)} min · "
        result = self._check(self.prs[number], name)
        self.calls.append({"pr": number, "tool": name, "result": result})
        return f"{result}\n\n[{ran}{self.clock.stamp()}]"

    def _check(self, pr: PullRequest, name: str) -> str:
        if name == "view_diff":
            return pr.sandbox.diff() or "(no changes)"
        if name == "view_log":
            return format_log(pr)
        if name == "rerun_tests":
            run = pr.sandbox.run_tests()
            return f"Tests {'PASSED' if run.passed else 'FAILED'}: {run.summary}\n{run.output}"
        return format_style_check(pr)


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
