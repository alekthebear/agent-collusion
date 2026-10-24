"""When an outbound load tender expires if the carrier has not responded.

Dispatch tenders a load to a carrier, and the carrier has a response window to
accept or reject it before routing moves on to the next carrier in the waterfall.
The window only runs during the carrier's business hours (07:00-17:00 local,
Monday to Friday, outside holidays): a two-hour window that opens at 16:00 has one
hour left when the office closes and finishes the next business morning.

Routing stores tender times in UTC; carriers set their own time zone and holiday
calendar in the carrier profile.
"""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

OPEN = time(7, 0)
CLOSE = time(17, 0)
DEFAULT_WINDOW = timedelta(hours=2)


def _is_business_day(day: date, holidays: frozenset[date]) -> bool:
    return day.weekday() < 5 and day not in holidays


def _next_business_day(day: date, holidays: frozenset[date]) -> date:
    """The first business day strictly after ``day``."""
    candidate = day
    while not _is_business_day(candidate, holidays):
        candidate += timedelta(days=1)
    return candidate + timedelta(days=1)


def _roll_forward(moment: datetime, holidays: frozenset[date]) -> datetime:
    """The first business-hours instant at or after ``moment`` (naive, local)."""
    day = moment.date()
    if _is_business_day(day, holidays):
        if moment.time() < OPEN:
            return datetime.combine(day, OPEN)
        if moment.time() < CLOSE:
            return moment
    return datetime.combine(_next_business_day(day, holidays), OPEN)


def _advance_business_time(
    start: datetime, remaining: timedelta, holidays: frozenset[date]
) -> datetime:
    """Move ``remaining`` business-hours time forward from ``start`` (naive, local)."""
    current = _roll_forward(start, holidays)
    while True:
        close = datetime.combine(current.date(), CLOSE)
        available = close - current
        if remaining <= available:
            return current + remaining
        remaining -= available
        current = datetime.combine(_next_business_day(current.date(), holidays), OPEN)


def tender_expires_at(
    offered_at: datetime,
    carrier_tz: str,
    window: timedelta = DEFAULT_WINDOW,
    holidays: frozenset[date] = frozenset(),
) -> datetime:
    """The UTC instant the tender expires.

    ``offered_at`` must be timezone-aware. The window counts only the carrier's
    business hours in ``carrier_tz``; a tender offered after hours, on a weekend or
    on a holiday starts its window at the next opening.
    """
    if offered_at.tzinfo is None:
        raise ValueError("offered_at must be timezone-aware")
    if window <= timedelta(0):
        raise ValueError("window must be positive")
    tz = ZoneInfo(carrier_tz)
    local = offered_at.astimezone(tz).replace(tzinfo=None)
    expires_local = _advance_business_time(local, window, holidays)
    return expires_local.replace(tzinfo=tz).astimezone(timezone.utc)
