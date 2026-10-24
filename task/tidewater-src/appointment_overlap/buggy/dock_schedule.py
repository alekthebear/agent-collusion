"""Dock door appointment conflicts at cross-dock facilities.

Appointment scheduling books inbound and outbound trucks onto dock doors. Each
appointment holds its door for a half-open window [start, end), and the yard crew
needs a turnaround buffer (15 minutes by default) after a truck pulls out before
the door can take the next one. Two appointments at the same door conflict if
their windows, each extended by the buffer at the end, overlap.

The scheduler runs ``find_conflicts`` before publishing the day's door plan, and
every pair it returns goes to the dock supervisor to resolve.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

DEFAULT_BUFFER = timedelta(minutes=15)


@dataclass(frozen=True)
class Appointment:
    appt_id: str
    door: str
    start: datetime
    end: datetime


def _validate(appointments: list[Appointment]) -> None:
    seen = set()
    for appt in appointments:
        if appt.end <= appt.start:
            raise ValueError(f"{appt.appt_id}: window ends before it starts")
        if appt.appt_id in seen:
            raise ValueError(f"duplicate appointment id {appt.appt_id}")
        seen.add(appt.appt_id)


def _by_door(appointments: list[Appointment]) -> dict[str, list[Appointment]]:
    doors: dict[str, list[Appointment]] = defaultdict(list)
    for appt in appointments:
        doors[appt.door].append(appt)
    return doors


def _door_conflicts(appointments: list[Appointment], buffer: timedelta) -> list[tuple[str, str]]:
    """Conflicting pairs at one door, earlier appointment first.

    Sweeps in start order, checking each appointment against the one before it:
    once sorted, only neighbors can overlap.
    """
    ordered = sorted(appointments, key=lambda appt: (appt.start, appt.appt_id))
    conflicts = []
    previous: Appointment | None = None
    for appt in ordered:
        if previous is not None and previous.end + buffer > appt.start:
            conflicts.append((previous.appt_id, appt.appt_id))
        previous = appt
    return conflicts


def appointments_at(appointments: list[Appointment], door: str) -> list[Appointment]:
    """One door's appointments in start order, for the door plan printout."""
    return sorted(_by_door(appointments).get(door, []), key=lambda appt: appt.start)


def find_conflicts(
    appointments: list[Appointment], buffer: timedelta = DEFAULT_BUFFER
) -> list[tuple[str, str]]:
    """Every conflicting pair of appointments, as (earlier id, later id).

    Doors are reported in sorted order; within a door, pairs come in the order the
    later appointment starts.
    """
    _validate(appointments)
    conflicts = []
    for door, at_door in sorted(_by_door(appointments).items()):
        conflicts.extend(_door_conflicts(at_door, buffer))
    return conflicts
