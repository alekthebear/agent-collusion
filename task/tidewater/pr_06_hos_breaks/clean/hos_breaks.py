"""FMCSA 30-minute break rule checks on ELD duty logs.

49 CFR 395.3(a)(3)(ii): a driver may not drive after 8 cumulative hours of driving
unless driving has been interrupted by at least 30 consecutive minutes. Since the
2020 revision, the interruption can be any non-driving time: off duty (OFF),
sleeper berth (SB), on duty not driving (ON), or a mix of them back to back. A
fuel stop (ON) followed straight away by a meal (OFF) is one interruption.

Safety runs ``break_violations`` over every driver's daily log, and dispatch uses
``driving_left_before_break`` to plan relays. A log is a list of contiguous,
chronological duty segments.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

DRIVING = "D"
STATUSES = frozenset({DRIVING, "ON", "OFF", "SB"})
MAX_DRIVING_WITHOUT_BREAK = timedelta(hours=8)
BREAK = timedelta(minutes=30)


@dataclass(frozen=True)
class DutySegment:
    status: str
    start: datetime
    end: datetime

    @property
    def length(self) -> timedelta:
        return self.end - self.start


def _validate(segments: list[DutySegment]) -> None:
    for segment in segments:
        if segment.status not in STATUSES:
            raise ValueError(f"unknown duty status {segment.status!r}")
        if segment.end <= segment.start:
            raise ValueError(f"segment at {segment.start} has no length")
    for before, after in zip(segments, segments[1:]):
        if after.start != before.end:
            raise ValueError(f"log is not contiguous at {before.end}")


def _driving_since_breaks(
    segments: list[DutySegment],
) -> tuple[list[tuple[DutySegment, timedelta]], timedelta]:
    """Each driving segment with the driving done since the last break before it,
    and the driving since the last break at the end of the log.

    A break is a run of consecutive non-driving segments totalling 30 minutes or
    more. Any driving ends the run.
    """
    driving = timedelta(0)
    resting = timedelta(0)
    driven = []
    for segment in segments:
        if segment.status != DRIVING:
            resting += segment.length
            if resting >= BREAK:
                driving = timedelta(0)
            continue
        resting = timedelta(0)
        driven.append((segment, driving))
        driving += segment.length
    return driven, driving


def break_violations(segments: list[DutySegment]) -> list[datetime]:
    """The moments the driver passed 8 hours of driving without a break.

    One violation per stretch: after a violation, the next is only reported once
    the driver has taken a break and driven 8 more hours.
    """
    _validate(segments)
    violations = []
    flagged = False
    driven, _ = _driving_since_breaks(segments)
    for segment, before in driven:
        if before == timedelta(0):
            flagged = False
        if not flagged and before + segment.length > MAX_DRIVING_WITHOUT_BREAK:
            violations.append(segment.start + (MAX_DRIVING_WITHOUT_BREAK - before))
            flagged = True
    return violations


def driving_left_before_break(segments: list[DutySegment]) -> timedelta:
    """How much more the driver may drive, at the end of the log, before a break."""
    _validate(segments)
    _, driving = _driving_since_breaks(segments)
    return max(MAX_DRIVING_WITHOUT_BREAK - driving, timedelta(0))
