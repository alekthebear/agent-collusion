"""Receiving windows at consignee facilities, and how an ETA sits against them.

Facilities publish receiving hours in their own local time, e.g. 08:00-16:00, or
22:00-06:00 for night receiving (the window closes the next morning). Dispatch
compares each truck's ETA, which routing computes in UTC, against the window to
decide whether to call ahead, re-sequence stops or book a new appointment.

All durations here are real elapsed time. A night window that spans the autumn
clock change is nine hours long, not eight.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

EARLY = "early"
ON_TIME = "on_time"
LATE = "late"


@dataclass(frozen=True)
class Window:
    opens: datetime  # aware, facility local time
    closes: datetime

    @property
    def zone(self) -> ZoneInfo:
        return self.opens.tzinfo


def receiving_window(day: date, open_at: time, close_at: time, facility_tz: str) -> Window:
    """The window that opens on ``day``; a close at or before the open is next day."""
    zone = ZoneInfo(facility_tz)
    opens = datetime.combine(day, open_at, tzinfo=zone)
    close_day = day + timedelta(days=1) if close_at <= open_at else day
    closes = datetime.combine(close_day, close_at, tzinfo=zone)
    return Window(opens, closes)


def _require_aware(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("ETA must be timezone-aware")
    return moment


def _elapsed_minutes(start: datetime, end: datetime) -> float:
    """Minutes from ``start`` to ``end``, measured in UTC."""
    return (end.astimezone(timezone.utc) - start.astimezone(timezone.utc)).total_seconds() / 60


def window_minutes(window: Window) -> float:
    return _elapsed_minutes(window.opens, window.closes)


def slack_minutes(eta: datetime, window: Window) -> float:
    """Minutes from the ETA until the window closes; negative means late."""
    local_eta = _require_aware(eta).astimezone(window.zone)
    return _elapsed_minutes(local_eta, window.closes)


def window_status(eta: datetime, window: Window) -> str:
    """EARLY before the window opens, LATE after it closes, else ON_TIME."""
    local_eta = _require_aware(eta).astimezone(window.zone)
    if _elapsed_minutes(window.opens, local_eta) < 0:
        return EARLY
    if slack_minutes(eta, window) < 0:
        return LATE
    return ON_TIME


def latest_departure(window: Window, drive_minutes: float) -> datetime:
    """The latest UTC departure from the previous stop that still makes the window."""
    return window.closes.astimezone(timezone.utc) - timedelta(minutes=drive_minutes)
