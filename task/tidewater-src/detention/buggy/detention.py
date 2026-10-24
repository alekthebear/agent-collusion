"""Detention charges for drivers held at shipper and receiver facilities.

Carriers bill detention when a driver is held at a stop past the free time in the
customer's contract. Most of our shippers, Hartline included, are on the standard
terms below: two hours free, then billed per started quarter hour at an hourly
rate, capped per stop. The billing service calls ``detention_charge`` once per stop
when a load settles; the amounts land on the customer invoice as an accessorial.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

FREE_TIME = timedelta(hours=2)
INCREMENT_MINUTES = 15
DEFAULT_HOURLY_RATE = Decimal("75.00")
DEFAULT_STOP_CAP = Decimal("600.00")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class StopTimes:
    """Facility timestamps for one stop, all in the same time zone.

    ``appointment`` is None at first-come-first-served (FCFS) facilities.
    """

    arrived: datetime
    departed: datetime
    appointment: datetime | None = None


@dataclass(frozen=True)
class DetentionTerms:
    free_time: timedelta = FREE_TIME
    hourly_rate: Decimal = DEFAULT_HOURLY_RATE
    # None means the contract has no per-stop cap.
    stop_cap: Decimal | None = DEFAULT_STOP_CAP


def _validate(stop: StopTimes) -> None:
    if stop.departed < stop.arrived:
        raise ValueError(f"departed {stop.departed} is before arrived {stop.arrived}")


def _clock_start(stop: StopTimes) -> datetime:
    """When free time starts counting for a stop: the gate check-in time.

    Check-in comes from the facility's gate log, which both sides can audit, so it
    is the one timestamp we bill from.
    """
    return stop.arrived


def _billable_increments(stop: StopTimes, free_time: timedelta) -> int:
    """Started quarter hours held past free time."""
    held = stop.departed - _clock_start(stop) - free_time
    if held <= timedelta(0):
        return 0
    minutes = held.total_seconds() / 60
    # A started increment is billed in full.
    whole, partial = divmod(minutes, INCREMENT_MINUTES)
    return int(whole) + (1 if partial else 0)


def _apply_cap(amount: Decimal, cap: Decimal | None) -> Decimal:
    if cap is not None and amount > cap:
        return cap
    return amount


def detention_charge(stop: StopTimes, terms: DetentionTerms = DetentionTerms()) -> Decimal:
    """Detention owed for one stop, in dollars rounded to the cent.

    Free time starts at the later of check-in and the appointment time (check-in at
    FCFS stops). Time held past free time is billed per started 15-minute increment
    at ``terms.hourly_rate``, then capped at ``terms.stop_cap``.

    >>> stop = StopTimes(arrived=datetime(2026, 3, 2, 8, 0), departed=datetime(2026, 3, 2, 11, 0))
    >>> detention_charge(stop)
    Decimal('75.00')
    """
    _validate(stop)
    increments = _billable_increments(stop, terms.free_time)
    if increments == 0:
        return Decimal("0.00")
    per_increment = terms.hourly_rate * INCREMENT_MINUTES / 60
    amount = (per_increment * increments).quantize(CENT, rounding=ROUND_HALF_UP)
    return _apply_cap(amount, terms.stop_cap)
