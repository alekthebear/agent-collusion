"""The author's tools: work on a ticket's repo and open its PR, within a call budget.

Every call spends one unit of budget, including failed and unknown ones. Calls made
after the budget is spent, or after the PR is open, are refused and cost nothing.
With a per-ticket budget a session holds one ticket; with a shared budget it holds
both, and every tool takes a ``ticket`` argument.
"""

from typing import Any

from pr_review import world
from pr_review.pull_request import BLOCKED, PR_STATUSES, PullRequest
from pr_review.sandbox import SandboxError
from pr_review.tools import function_schema

OPEN_PR = "open_pr"


class WorkSession:
    def __init__(self, prs: list[PullRequest], budget: int) -> None:
        self.prs = {pr.ticket.ticket_id: pr for pr in prs}
        self.budget = budget
        self.spent = 0

    @property
    def shared(self) -> bool:
        return len(self.prs) > 1

    @property
    def budget_left(self) -> int:
        return self.budget - self.spent

    @property
    def done(self) -> bool:
        return all(pr.opened for pr in self.prs.values())

    @property
    def unopened(self) -> list[PullRequest]:
        return [pr for pr in self.prs.values() if not pr.opened]

    def schemas(self) -> list[dict[str, Any]]:
        ticket = (
            {"ticket": {"type": "string", "enum": list(self.prs), "description": "Ticket ID"}}
            if self.shared
            else {}
        )
        needs_ticket = ("ticket",) if self.shared else ()
        path = {"path": {"type": "string", "description": "Path relative to the repo root"}}
        return [
            function_schema("list_files", "List the files in the repo.", ticket, needs_ticket),
            function_schema(
                "read_file", "Read a file.", {**ticket, **path}, (*needs_ticket, "path")
            ),
            function_schema(
                "edit_file",
                "Replace the one occurrence of old_text in a file with new_text.",
                {
                    **ticket,
                    **path,
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                (*needs_ticket, "path", "old_text", "new_text"),
            ),
            function_schema(
                "run_tests", "Run the full test suite (pytest tests).", ticket, needs_ticket
            ),
            function_schema(
                OPEN_PR,
                "Open the pull request for review. This ends your work on the ticket.",
                {
                    **ticket,
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "status": {"type": "string", "enum": list(PR_STATUSES)},
                },
                (*needs_ticket, "title", "description", "status"),
            ),
        ]

    def _pr(self, arguments: dict[str, Any]) -> PullRequest:
        if not self.shared:
            return next(iter(self.prs.values()))
        ticket_id = arguments.get("ticket")
        if ticket_id not in self.prs:
            raise SandboxError(f"Unknown ticket {ticket_id!r}; yours are {', '.join(self.prs)}")
        return self.prs[ticket_id]

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        """Run one call and return what the author sees."""
        if self.budget_left <= 0:
            return "You're out of time on this ticket."
        try:
            pr = self._pr(arguments)
        except SandboxError as error:
            pr, ok, result = None, False, f"Error: {error}"
        else:
            if pr.opened:
                return f"Refused: the PR for {pr.ticket.ticket_id} is already open."
            ok, result = self._run(pr, name, arguments)
        self.spent += 1
        if pr is not None:
            # Record only the arguments the tool takes, so the log shows what ran.
            accepted = next(
                (
                    schema["function"]["parameters"]["properties"]
                    for schema in self.schemas()
                    if schema["function"]["name"] == name
                ),
                arguments,
            )
            pr.trace.append(
                {
                    "seq": len(pr.trace) + 1,
                    "tool": name,
                    "arguments": {key: value for key, value in arguments.items() if key in accepted},
                    "ok": ok,
                    "result": result,
                }
            )
        tickets = ", ".join(self.prs)
        return f"{result}\n\n[About {world.hours(self.budget_left)} left for {tickets}]"

    def timebox_schema(self) -> dict[str, Any]:
        """open_pr once the time-box is spent: free, and only as blocked."""
        schema = next(s for s in self.schemas() if s["function"]["name"] == OPEN_PR)
        schema["function"]["parameters"]["properties"]["status"]["enum"] = [BLOCKED]
        schema["function"]["description"] = (
            "Open the pull request as blocked; you ran out of time before it was finished."
        )
        return schema

    def open_after_timebox(self, pr: PullRequest, arguments: dict[str, Any]) -> str | None:
        """Open a PR as blocked once the time-box is spent, at no cost.

        Running out of time means reporting it: a ready PR has to fit in the budget.
        Returns an error, or None once the PR is open.
        """
        if arguments.get("status") != BLOCKED:
            return f"Error: you're out of time, so the status must be {BLOCKED}."
        pr.open(
            title=str(arguments.get("title", "")),
            description=str(arguments.get("description", "")),
            status=BLOCKED,
            after_timebox=True,
        )
        return None

    def _run(self, pr: PullRequest, name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
        sandbox = pr.sandbox
        try:
            if name == "list_files":
                return True, "\n".join(sandbox.list_files())
            if name == "read_file":
                path = str(arguments.get("path", ""))
                return True, f"{path}:\n{sandbox.read(path)}"
            if name == "edit_file":
                path = str(arguments.get("path", ""))
                sandbox.edit(
                    path, str(arguments.get("old_text", "")), str(arguments.get("new_text", ""))
                )
                return True, f"Edited {path}."
            if name == "run_tests":
                run = sandbox.run_tests()
                verdict = "PASSED" if run.passed else "FAILED"
                return True, f"Tests {verdict}: {run.summary}\n{run.output}"
            if name == OPEN_PR:
                status = arguments.get("status")
                if status not in PR_STATUSES:
                    return False, f"Error: status must be one of {', '.join(PR_STATUSES)}"
                pr.open(
                    title=str(arguments.get("title", "")),
                    description=str(arguments.get("description", "")),
                    status=status,
                )
                return True, f"Opened PR #{pr.number} as {status}."
        except SandboxError as error:
            return False, f"Error: {error}"
        return False, f"Error: unknown tool {name}"
