"""A ticket's pull request: the author's sandbox, trace, and what was opened."""

from dataclasses import dataclass, field
from typing import Any

from pr_review.sandbox import Sandbox, TestRun

READY = "ready"
BLOCKED = "blocked"
PR_STATUSES = (READY, BLOCKED)


@dataclass
class Ticket:
    task: dict[str, Any]
    author: str
    reviewer: str
    difficulty: str
    budget: int
    # MH carryover: the day (episode) whose PR for this ticket wasn't approved, and the
    # review that sent it back. 0 for a new ticket.
    carried_from: int = 0
    carry_reason: str = ""

    @property
    def ticket_id(self) -> str:
        return self.task["ticket"]

    @property
    def number(self) -> int:
        """The PR number, which reuses the ticket number."""
        return int(self.ticket_id.split("-")[1])


@dataclass
class PullRequest:
    ticket: Ticket
    sandbox: Sandbox
    # Every worker tool call: {seq, tool, arguments, ok, result}.
    trace: list[dict[str, Any]] = field(default_factory=list)
    opened: bool = False
    # True when the author opened it only after the time-box ran out.
    opened_after_timebox: bool = False
    title: str = ""
    description: str = ""
    status: str = BLOCKED
    # For a confederate's PR: the scripted violation, or "clean". None otherwise.
    planted: str | None = None
    # Visible tests and hidden tests, as of opening.
    tests_at_open: TestRun | None = None
    hidden_at_open: TestRun | None = None
    # Conditions that change which rules apply to this PR.
    house_rules: bool = False

    @property
    def kind(self) -> str:
        """standard, misrouted (the fix belongs to another team) or contradiction."""
        return self.ticket.task.get("kind", "standard")

    @property
    def number(self) -> int:
        return self.ticket.number

    def open(self, *, title: str, description: str, status: str, after_timebox: bool = False) -> None:
        self.opened = True
        self.opened_after_timebox = after_timebox
        self.title = title
        self.description = description
        self.status = status
        self.tests_at_open = self.sandbox.run_tests()
        self.hidden_at_open = self.sandbox.run_hidden_tests()

    def header(self) -> str:
        """What a reviewer sees for free: ticket, time it had, title, description, status."""
        task = self.ticket.task
        return "\n".join(
            [
                f"PR #{self.number} by {self.ticket.author.capitalize()} "
                f"for {task['ticket']}: {task['title']}",
                f"Linear: {task['text']}",
                f"Time the author had for it: about {_hours(self.ticket.budget)}",
                f"Status: {self.status}",
                f"Title: {self.title}",
                f"Description: {self.description}",
            ]
        )


def _hours(steps: int) -> str:
    from pr_review.world import hours

    return hours(steps)
