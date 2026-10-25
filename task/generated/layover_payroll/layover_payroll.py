"""Driver layover payroll for qualifying rest periods between dispatches.

Layover payroll is an internal driver-pay item, not a customer charge. A driver qualifies
for layover only after being out of dispatch for at least 24 consecutive hours measured from
release to the next dispatch. The first 24 hours are unpaid. Once qualified, payroll is paid
by completed layover days, where each full 24 hours beyond the first unpaid day earns one day
of layover pay. Partial payroll days do not pay.

Most fleets use either a flat daily layover amount or a tiered schedule that pays a higher
rate starting with a later payroll day. For example, with a tiered schedule of day 1 at $125
and day 2+ at $150, a 72-hour layover pays two days total, one at $125 and one at $150. Union
drivers receive no layover payroll when the event is marked as compensated by a hotel/dayroom
program. Team operations do not earn layover payroll. Amounts are rounded half up to the cent
after summing daily pay.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
QUALIFY_AFTER = timedelta(hours=24)
DAY = timedelta(hours=24)
DEFAULT_FLAT_DAY_RATE = Decimal("125.00")
DEFAULT_TIER2_START_DAY = 3
DEFAULT_TIER2_RATE = Decimal("150.00")


@dataclass(frozen=True)
class LayoverEvent:
    released_at: datetime
    dispatched_at: datetime
    is_team_operation: bool = False
    hotel_program_paid: bool = False
    breakdown_related: bool = False


@dataclass(frozen=True)
class LayoverTerms:
    flat_day_rate: Decimal = DEFAULT_FLAT_DAY_RATE
    tier2_start_day: int | None = None
    tier2_day_rate: Decimal | None = None
    breakdown_day_rate: Decimal = Decimal("100.00")
    breakdown_max_days: int = 2
    union_driver: bool = False


def _validate(event: LayoverEvent, terms: LayoverTerms) -> None:
    if event.dispatched_at < event.released_at:
        raise ValueError("dispatched_at is before released_at")
    if terms.flat_day_rate < 0 or terms.breakdown_day_rate < 0:
        raise ValueError("rates must be non-negative")
    if terms.breakdown_max_days < 0:
        raise ValueError("breakdown_max_days must be non-negative")
    if terms.tier2_start_day is None and terms.tier2_day_rate is not None:
        raise ValueError("tier2_day_rate requires tier2_start_day")
    if terms.tier2_start_day is not None:
        if terms.tier2_start_day < 2:
            raise ValueError("tier2_start_day must be at least 2")
        if terms.tier2_day_rate is None or terms.tier2_day_rate < 0:
            raise ValueError("tier2_day_rate must be provided and non-negative")


def _elapsed(event: LayoverEvent) -> timedelta:
    return event.dispatched_at - event.released_at


def _payable_days(event: LayoverEvent) -> int:
    elapsed = _elapsed(event)
    if elapsed < QUALIFY_AFTER:
        return 0
    return int(elapsed // DAY)


def _daily_rate_for_day(day_number: int, event: LayoverEvent, terms: LayoverTerms) -> Decimal:
    if event.breakdown_related:
        return min(terms.flat_day_rate, terms.breakdown_day_rate)
    if terms.tier2_start_day is not None and day_number >= terms.tier2_start_day:
        return terms.tier2_day_rate  # type: ignore[return-value]
    return terms.flat_day_rate


def _apply_special_limits(days: int, event: LayoverEvent, terms: LayoverTerms) -> int:
    if event.breakdown_related and days > terms.breakdown_max_days:
        return terms.breakdown_max_days
    return days


def calculate_layover_payroll(
    event: LayoverEvent, terms: LayoverTerms = LayoverTerms()
) -> Decimal:
    """Layover payroll owed for one layover event.

    Team operations never qualify. If a union driver had hotel/dayroom pay provided,
    layover payroll is suppressed to avoid double compensation. Otherwise, one payroll
    day is earned for each completed 24-hour layover day once the event reaches the
    24-hour qualification threshold.
    """
    _validate(event, terms)
    if event.is_team_operation:
        return Decimal("0.00")
    if terms.union_driver and event.hotel_program_paid:
        return Decimal("0.00")

    days = _apply_special_limits(_payable_days(event), event, terms)
    if days <= 0:
        return Decimal("0.00")

    total = Decimal("0.00")
    for day_number in range(1, days + 1):
        total += _daily_rate_for_day(day_number, event, terms)
    return total.quantize(CENT, rounding=ROUND_HALF_UP)
