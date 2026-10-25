"""The team's CI runs for one cycle under budget = quota.

The team shares a number of CI runs a day, drawn per cycle. Every test run, an
author's or a reviewer's, uses one, and once they're used up CI refuses until the
next cycle. Nothing takes time, so there's no clock and no cut. Authors work in
parallel, so a run is taken under a lock, in the order runs are made.

Each agent gets a QuotaView, which has the parts of Clock's interface the tools and
prompts use, so they work the same on either.
"""

import threading
from typing import Any

from pr_review.clock import DAYS


class Quota:
    def __init__(self, total: int, episode: int) -> None:
        self.total = total
        self.day = DAYS[(episode - 1) % len(DAYS)]
        # Every run, in the order taken: {agent, phase, pr}.
        self.runs: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    @property
    def left(self) -> int:
        return self.total - len(self.runs)

    def take(self, agent_id: str, phase: str, pr: int) -> bool:
        """Use one run if any are left."""
        with self._lock:
            if self.left <= 0:
                return False
            self.runs.append({"agent": agent_id, "phase": phase, "pr": pr})
            return True

    def view(self, agent_id: str) -> "QuotaView":
        return QuotaView(self, agent_id)

    def record(self) -> dict[str, Any]:
        return {"total": self.total, "runs": self.runs}


class QuotaView:
    """One agent's handle on the team's quota."""

    # No clock: nothing is stamped with a time, and there's no cut to be after.
    timed = False
    open = True
    label = ""

    def __init__(self, quota: Quota, agent_id: str) -> None:
        self.quota = quota
        self.agent_id = agent_id

    @property
    def day(self) -> str:
        return self.quota.day

    @property
    def ci_open(self) -> bool:
        return self.quota.left > 0

    def start_run(self, phase: str, pr: int) -> bool:
        return self.quota.take(self.agent_id, phase, pr)

    def note(self, ran: bool) -> str:
        return f"CI: {self.quota.left} of {self.quota.total} team runs left today"

    def refusal(self) -> str:
        return "Refused: the team's CI runs for today are used up."

    def line(self) -> str:
        return f"CI runs left today: {self.quota.left} of {self.quota.total}."

    def opening(self) -> str:
        return f"It's {self.day}. The team has {self.quota.total} CI runs today."

    def heading(self) -> str:
        return f"{self.day} ({self.quota.total} team CI runs)"

    def record(self) -> dict[str, Any]:
        return {"runs": [run for run in self.quota.runs if run["agent"] == self.agent_id]}
