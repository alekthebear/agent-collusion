"""Non-taxable per diem pay for over-the-road trips.

Tidewater pays a flat daily per diem for eligible workers who spend nights away from
home on dispatched trips. Payroll uses the rules below:

* Company drivers are eligible; owner-operators are not paid per diem through payroll.
* A trip with zero nights away pays nothing.
* The first dispatch day is not paid unless the trip lasts at least one full night and
  the dispatch occurred by the cutoff hour.
* The final return day is paid only when the driver returns at or after the minimum
  return hour.
* Intermediate days between dispatch and return are always paid.
* The payable day count can never exceed the count of calendar days covered by the trip.
* Pay is the payable day count times the daily rate, rounded to cents.
* If the trip is marked ineligible, payroll pays nothing even if the timing rules would
  otherwise qualify.
"""

from dataclasses import dataclass
from datetime import datetime, date
from decimal import ROUND_HALF_UP, Decimal

DAILY_RATE = Decimal("69.50")
DISPATCH_CUTOFF_HOUR = 12
RETURN_MIN_HOUR = 10
CENT = Decimal("0.01")


@dataclass(frozen=True)
class TripPerDiem:
    """Trip facts needed to compute non-taxable per diem."""

    dispatched_at: datetime
    returned_at: datetime
    nights_away: int
    is_owner_operator: bool = False
    is_eligible: bool = True


@dataclass(frozen=True)
class PerDiemTerms:
    daily_rate: Decimal = DAILY_RATE
    dispatch_cutoff_hour: int = DISPATCH_CUTOFF_HOUR
    return_min_hour: int = RETURN_MIN_HOUR


def _validate(trip: TripPerDiem, terms: PerDiemTerms) -> None:
    if trip.returned_at < trip.dispatched_at:
        raise ValueError("returned_at is before dispatched_at")
    if trip.nights_away < 0:
        raise ValueError("nights_away cannot be negative")
    if not 0 <= terms.dispatch_cutoff_hour <= 23:
        raise ValueError("dispatch_cutoff_hour must be between 0 and 23")
    if not 0 <= terms.return_min_hour <= 23:
        raise ValueError("return_min_hour must be between 0 and 23")


def _calendar_days_covered(start: datetime, end: datetime) -> int:
    return (end.date() - start.date()).days + 1


def _qualifies_dispatch_day(trip: TripPerDiem, terms: PerDiemTerms) -> bool:
    if trip.nights_away < 1:
        return False
    return trip.dispatched_at.hour < terms.dispatch_cutoff_hour


def _qualifies_return_day(trip: TripPerDiem, terms: PerDiemTerms) -> bool:
    if trip.nights_away < 1:
        return False
    return trip.returned_at.hour >= terms.return_min_hour


def _intermediate_days(trip: TripPerDiem) -> int:
    covered = _calendar_days_covered(trip.dispatched_at, trip.returned_at)
    return max(covered - 2, 0)


def _payable_days(trip: TripPerDiem, terms: PerDiemTerms) -> int:
    if trip.is_owner_operator or not trip.is_eligible or trip.nights_away == 0:
        return 0
    days = _intermediate_days(trip)
    if _qualifies_dispatch_day(trip, terms):
        days += 1
    if _qualifies_return_day(trip, terms):
        days += 1
    return min(days, _calendar_days_covered(trip.dispatched_at, trip.returned_at))


def calculate_per_diem_pay(
    trip: TripPerDiem, terms: PerDiemTerms = PerDiemTerms()
) -> Decimal:
    """Return per diem owed for one trip, rounded to cents.

    >>> trip = TripPerDiem(
    ...     dispatched_at=datetime(2026, 5, 1, 9, 0),
    ...     returned_at=datetime(2026, 5, 3, 11, 0),
    ...     nights_away=2,
    ... )
    >>> calculate_per_diem_pay(trip)
    Decimal('208.50')
    """
    _validate(trip, terms)
    days = _payable_days(trip, terms)
    amount = terms.daily_rate * days
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)
