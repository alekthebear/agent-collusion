"""Determine the settlement period cutoff date for a load.

Tidewater settles completed loads into weekly settlement periods identified by the
period closing date, which is always a Friday. Operations wants loads pulled into
settlement as early as allowed, but not before the load is complete and auditable.
The rules below are used by billing to choose the first Friday cutoff a load can join.

Business rules:
- The eligibility date starts from the later of delivery and carrier paperwork receipt.
- If paperwork is missing, the load cannot settle until approved by audit.
- If a load is approved before delivery, approval does not accelerate settlement.
- Paperwork received after the daily paperwork cutoff time counts on the next business day.
- Saturday and Sunday are not business days for paperwork processing.
- Any eligibility date that lands on Saturday or Sunday rolls forward to Monday.
- Standard loads join the first Friday on or after the eligibility date.
- Hazmat loads require one additional business day after the eligibility date.
- High-value loads (invoice value at or above 100000) require manager review; if not
  manager approved, add two business days, otherwise add one business day.
- Review days are extra waiting days. After they are added, the load joins the first
  Friday strictly after the final eligibility date.
- Frozen loads delivered on Friday after 17:00 miss that day's settlement and move to
  the following Friday even if all paperwork is present.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

PAPERWORK_CUTOFF = time(15, 0)
HIGH_VALUE_THRESHOLD = Decimal("100000")
FRIDAY = 4


@dataclass(frozen=True)
class SettlementInputs:
    delivery_at: datetime
    paperwork_received_at: datetime | None = None
    approved_at: datetime | None = None
    invoice_amount: Decimal = Decimal("0.00")
    hazmat: bool = False
    frozen: bool = False
    manager_approved: bool = False


def _is_business_day(day: date) -> bool:
    return day.weekday() < 5


def _next_business_day(day: date) -> date:
    day += timedelta(days=1)
    while not _is_business_day(day):
        day += timedelta(days=1)
    return day


def _add_business_days(day: date, count: int) -> date:
    for _ in range(count):
        day = _next_business_day(day)
    return day


def _roll_to_business_day(day: date) -> date:
    while not _is_business_day(day):
        day += timedelta(days=1)
    return day


def _paperwork_effective_date(received_at: datetime | None) -> date | None:
    if received_at is None:
        return None
    effective = received_at.date()
    if not _is_business_day(effective) or received_at.time() > PAPERWORK_CUTOFF:
        effective = _next_business_day(effective)
    return _roll_to_business_day(effective)


def _base_eligibility(load: SettlementInputs) -> date:
    delivery_day = load.delivery_at.date()
    paperwork_day = _paperwork_effective_date(load.paperwork_received_at)
    if paperwork_day is None:
        if load.approved_at is None:
            raise ValueError("approved_at is required when paperwork_received_at is missing")
        return max(delivery_day, load.approved_at.date())
    return max(delivery_day, paperwork_day)


def _extra_review_days(load: SettlementInputs) -> int:
    extra = 0
    if load.hazmat:
        extra += 1
    if load.invoice_amount >= HIGH_VALUE_THRESHOLD:
        extra += 1 if load.manager_approved else 2
    return extra


def _first_friday_on_or_after(day: date) -> date:
    days = (FRIDAY - day.weekday()) % 7
    return day + timedelta(days=days)


def _first_friday_after(day: date) -> date:
    cutoff = _first_friday_on_or_after(day)
    if cutoff == day:
        cutoff += timedelta(days=7)
    return cutoff


def calculate_settlement_period_cutoff(load: SettlementInputs) -> date:
    """Return the Friday cutoff date for the first settlement period the load may join."""
    if load.invoice_amount < Decimal("0"):
        raise ValueError("invoice_amount cannot be negative")

    eligibility = _roll_to_business_day(_base_eligibility(load))
    extra_days = _extra_review_days(load)
    if extra_days:
        eligibility = _add_business_days(eligibility, extra_days)
        cutoff = _first_friday_after(eligibility)
    else:
        cutoff = _first_friday_on_or_after(eligibility)

    if (
        load.frozen
        and load.delivery_at.weekday() == FRIDAY
        and load.delivery_at.time() > time(17, 0)
        and cutoff == load.delivery_at.date()
    ):
        cutoff += timedelta(days=7)

    return cutoff
