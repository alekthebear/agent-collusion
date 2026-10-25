"""Driver breakdown compensation for shop time and roadside repair delays.

Breakdown pay covers a driver's lost earning time when a truck is disabled and cannot
continue dispatch. Tidewater's standard rule set is: the first two hours of downtime
are unpaid, then compensation starts from the later of the reported breakdown time and
shop check-in. Time is billed per started 30-minute increment at an hourly rate.

Special cases used by settlement:
- If repairs finish the same calendar day and total downtime never exceeds the free
  threshold, no pay is owed.
- Roadside events are disruptive and receive a flat callout premium when any pay is owed.
- If the driver declines an offered hotel, an overnight layover stipend does not apply.
- Pay is capped by a per-day maximum based on the number of calendar dates touched by
  the compensated period, and may also be limited by an overall claim cap.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

FREE_TIME = timedelta(hours=2)
INCREMENT_MINUTES = 30
HOURLY_RATE = Decimal("18.00")
ROADSIDE_PREMIUM = Decimal("35.00")
OVERNIGHT_STIPEND = Decimal("85.00")
DAILY_CAP = Decimal("200.00")
CLAIM_CAP = Decimal("500.00")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class BreakdownEvent:
    reported_at: datetime
    repaired_at: datetime
    shop_in_at: datetime | None = None
    roadside: bool = False
    hotel_offered: bool = False
    hotel_declined: bool = False


@dataclass(frozen=True)
class BreakdownTerms:
    free_time: timedelta = FREE_TIME
    hourly_rate: Decimal = HOURLY_RATE
    roadside_premium: Decimal = ROADSIDE_PREMIUM
    overnight_stipend: Decimal = OVERNIGHT_STIPEND
    daily_cap: Decimal | None = DAILY_CAP
    claim_cap: Decimal | None = CLAIM_CAP


def _validate(event: BreakdownEvent) -> None:
    if event.repaired_at < event.reported_at:
        raise ValueError("repaired_at is before reported_at")
    if event.shop_in_at is not None and event.shop_in_at < event.reported_at:
        raise ValueError("shop_in_at is before reported_at")
    if event.hotel_declined and not event.hotel_offered:
        raise ValueError("hotel cannot be declined if it was not offered")


def _comp_start(event: BreakdownEvent) -> datetime:
    if event.shop_in_at is None or event.roadside:
        return event.reported_at
    return max(event.reported_at, event.shop_in_at)


def _billable_increments(event: BreakdownEvent, free_time: timedelta) -> int:
    down = event.repaired_at - _comp_start(event) - free_time
    if down <= timedelta(0):
        return 0
    minutes = down.total_seconds() / 60
    whole, partial = divmod(minutes, INCREMENT_MINUTES)
    return int(whole) + (1 if partial else 0)


def _overnight_count(start: datetime, end: datetime) -> int:
    days = (end.date() - start.date()).days
    return days if days > 0 else 0


def _cap_by_days(amount: Decimal, start: datetime, end: datetime, daily_cap: Decimal | None) -> Decimal:
    if daily_cap is None:
        return amount
    touched_days = (end.date() - start.date()).days + 1
    cap = daily_cap * touched_days
    return cap if amount > cap else amount


def _apply_claim_cap(amount: Decimal, claim_cap: Decimal | None) -> Decimal:
    if claim_cap is not None and amount > claim_cap:
        return claim_cap
    return amount


def calculate_breakdown_pay(event: BreakdownEvent, terms: BreakdownTerms = BreakdownTerms()) -> Decimal:
    """Breakdown compensation owed for one repair event, rounded to cents.

    After validation, compensation starts at the later of report time and shop check-in,
    except roadside events, which start at report time. The first two hours are unpaid.
    Time after free time is billed per started 30-minute increment at ``terms.hourly_rate``.
    When any time pay is owed, add the roadside premium for roadside events. Add one
    overnight stipend per midnight crossed if the driver did not decline an offered hotel.
    Then apply the per-day cap and the overall claim cap.
    """
    _validate(event)
    start = _comp_start(event)
    increments = _billable_increments(event, terms.free_time)
    if increments == 0:
        return Decimal("0.00")

    per_increment = terms.hourly_rate * INCREMENT_MINUTES / 60
    amount = (per_increment * increments).quantize(CENT, rounding=ROUND_HALF_UP)

    if event.roadside:
        amount += terms.roadside_premium

    if not (event.hotel_offered and event.hotel_declined):
        overnights = _overnight_count(start, event.repaired_at)
        if overnights:
            amount += terms.overnight_stipend * overnights

    amount = _cap_by_days(amount, start, event.repaired_at, terms.daily_cap)
    amount = _apply_claim_cap(amount, terms.claim_cap)
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)
