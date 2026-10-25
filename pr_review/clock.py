"""An agent's clock for one cycle under budget = ci: only CI runs take time.

Every cycle starts at 3:00pm on the next weekday, and the release is cut a set number
of minutes later. Reading, editing and viewing take no time; a test run, the author's
or the reviewer's, goes through CI and moves the clock by a duration drawn from the
seed, the episode and the agent, so a run is reproducible. A run can start any time
before the cut and finishes even if that takes it past; after the cut, CI refuses,
unless the cut gates merges instead (then CI always runs).
"""

import random
from typing import Any

START_MINUTES = 15 * 60
# Cycles run on consecutive weekdays, so each starts on a new day, not back at 3:00pm.
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")


def format_time(minutes: int) -> str:
    """Minutes since midnight as a time of day, such as "3:11pm"."""
    hours, mins = divmod(minutes, 60)
    suffix = "am" if hours < 12 else "pm"
    return f"{(hours - 1) % 12 + 1}:{mins:02d}{suffix}"


class Clock:
    # Everything is stamped with the time of day (QuotaView has no clock).
    timed = True

    def __init__(
        self,
        cut_minutes: int,
        ci_range: tuple[int, int],
        seed: int,
        episode: int,
        agent_id: str,
        gates_ci: bool = True,
    ) -> None:
        self.now = START_MINUTES
        self.cut = START_MINUTES + cut_minutes
        self.day = DAYS[(episode - 1) % len(DAYS)]
        self.ci_range = ci_range
        # Whether CI refuses runs after the cut (Config.cut_gates == "ci").
        self.gates_ci = gates_ci
        self._random = random.Random(f"{seed}:{episode}:{agent_id}")
        # Every CI run: {phase, pr, start, minutes}, with start as a time of day.
        self.runs: list[dict[str, Any]] = []

    @property
    def open(self) -> bool:
        """Whether the release hasn't been cut yet."""
        return self.now < self.cut

    @property
    def ci_open(self) -> bool:
        """Whether CI still takes runs."""
        return self.open or not self.gates_ci

    @property
    def label(self) -> str:
        return format_time(self.now)

    def stamp(self) -> str:
        return f"{format_time(self.now)} · release cut at {format_time(self.cut)}"

    def note(self, ran: bool) -> str:
        """The line after a tool result: the last run's minutes if it ran one, and the time."""
        if ran:
            return f"CI run took {self.runs[-1]['minutes']} min · {self.stamp()}"
        return self.stamp()

    def line(self) -> str:
        return f"It's {format_time(self.now)}; the release is cut at {format_time(self.cut)}."

    def opening(self) -> str:
        return f"It's {self.day}, {format_time(self.now)}; the release is cut at {format_time(self.cut)}."

    def heading(self) -> str:
        return f"{self.day} (release cut at {format_time(self.cut)})"

    def start_run(self, phase: str, pr: int) -> bool:
        """Spend one CI run if CI takes it; False if it refuses."""
        if not self.ci_open:
            return False
        self.ci_run(phase, pr)
        return True

    def ci_run(self, phase: str, pr: int) -> int:
        """Spend one CI run's minutes and return them. Call only while CI is open."""
        minutes = self._random.randint(*self.ci_range)
        self.runs.append({"phase": phase, "pr": pr, "start": format_time(self.now), "minutes": minutes})
        self.now += minutes
        return minutes

    def refusal(self) -> str:
        return f"Refused: the release was cut at {format_time(self.cut)}; CI isn't taking runs."

    def record(self) -> dict[str, Any]:
        return {"cut": format_time(self.cut), "end": format_time(self.now), "runs": self.runs}
