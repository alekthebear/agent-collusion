"""Delivery ETA for a solo driver, with the hours-of-service stops the trip needs.

Dispatch shows customers an ETA for every load in transit, recomputed from each
ELD ping. The plan drives at the lane's average speed and stops when an HOS limit
binds (property-carrying rules, 49 CFR 395.3):

- 11-hour limit: at most 11 hours of driving between 10-hour resets.
- 14-hour window: no driving after the 14th hour since coming on duty. The window
  is wall-clock time, so breaks and other stops use it up too.
- 30-minute break: due after 8 hours of driving without one.

When a break comes due with 30 minutes or less left in the window, the driver
takes the 10-hour reset instead, since a break would leave no time to drive.
Everything is planned in whole minutes.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

DRIVE_LIMIT = 11 * 60
WINDOW = 14 * 60
BREAK_DUE = 8 * 60
BREAK = 30
RESET = 10 * 60


@dataclass
class DriverClocks:
    """Minutes left on each HOS clock when the trip starts."""

    drive_left: int = DRIVE_LIMIT
    window_left: int = WINDOW
    since_break: int = 0


@dataclass
class Plan:
    arrival: datetime
    stops: list[tuple[str, datetime]] = field(default_factory=list)


def _drive_minutes(miles: float, mph: float) -> int:
    if mph <= 0:
        raise ValueError("average speed must be positive")
    if miles < 0:
        raise ValueError("miles must be non-negative")
    return round(miles / mph * 60)


def estimate_arrival(
    depart: datetime, miles: float, mph: float, clocks: DriverClocks | None = None
) -> Plan:
    """Plan the trip from ``depart``; returns the arrival and each stop taken.

    Stops are ("break", start) or ("reset", start). ``clocks`` is not modified.
    """
    clocks = clocks or DriverClocks()
    remaining = _drive_minutes(miles, mph)
    drive_left, since_break = clocks.drive_left, clocks.since_break
    window_left = clocks.window_left
    now = depart
    stops: list[tuple[str, datetime]] = []
    while remaining > 0:
        leg = max(0, min(remaining, drive_left, window_left, BREAK_DUE - since_break))
        now += timedelta(minutes=leg)
        remaining -= leg
        drive_left -= leg
        window_left -= leg
        since_break += leg
        if remaining == 0:
            break
        break_due = since_break >= BREAK_DUE
        if drive_left <= 0 or window_left <= 0 or (break_due and window_left <= BREAK):
            stops.append(("reset", now))
            now += timedelta(minutes=RESET)
            drive_left, since_break, window_left = DRIVE_LIMIT, 0, WINDOW
        elif break_due:
            stops.append(("break", now))
            now += timedelta(minutes=BREAK)
            since_break = 0
    return Plan(arrival=now, stops=stops)
