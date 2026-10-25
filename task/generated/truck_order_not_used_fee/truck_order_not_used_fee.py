"""Truck-order-not-used (TONU) fees for canceled truckload moves.

A TONU charge compensates a carrier when a truck was committed but the load does
not move. Tidewater's truckload contracts do not use one universal rule, so this
module implements the standard customer formula used by the billing service.

Business rules:
- If the truck was actually loaded, TONU does not apply.
- A cancellation with no truck assigned is free.
- If the carrier arrives on site before cancellation, bill the full agreed TONU.
- Otherwise, bill by dispatch milestone and timing before the appointment:
  no dispatch = 0%; dispatched = 35%; driver assigned = 60%; en route = 85%.
- If cancellation occurs less than 2 hours before appointment, raise the percent
  to at least 90%. If after the appointment time, use 100%.
- Deadhead pay is added when the truck traveled before cancellation: mileage times
  the contract deadhead rate, with miles rounded up to the next whole mile.
- The total fee is capped at the contract full TONU plus deadhead, except when the
  contract marks TONU as non-stackable with deadhead, in which case bill the larger
  of base TONU and deadhead only.
- Contracts may specify a minimum billed TONU whenever any TONU percent applies.
- Amounts are rounded to the nearest cent with half-up rounding.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
DEFAULT_TONU = Decimal("250.00")
DEFAULT_DEADHEAD_RATE = Decimal("2.10")


@dataclass(frozen=True)
class TruckOrderEvent:
    appointment: datetime
    canceled_at: datetime
    dispatch_sent_at: datetime | None = None
    driver_assigned_at: datetime | None = None
    en_route_at: datetime | None = None
    arrived_at_shipper_at: datetime | None = None
    loaded: bool = False
    truck_assigned: bool = True
    deadhead_miles: Decimal = Decimal("0")


@dataclass(frozen=True)
class TonuTerms:
    full_tonu: Decimal = DEFAULT_TONU
    deadhead_rate: Decimal = DEFAULT_DEADHEAD_RATE
    minimum_tonu: Decimal = Decimal("75.00")
    stack_deadhead_with_tonu: bool = True


def _validate(event: TruckOrderEvent, terms: TonuTerms) -> None:
    if event.deadhead_miles < 0:
        raise ValueError("deadhead_miles cannot be negative")
    if terms.full_tonu < 0 or terms.deadhead_rate < 0 or terms.minimum_tonu < 0:
        raise ValueError("terms cannot contain negative amounts")
    milestones = [
        event.dispatch_sent_at,
        event.driver_assigned_at,
        event.en_route_at,
        event.arrived_at_shipper_at,
    ]
    prev = None
    for mark in milestones:
        if mark is None:
            continue
        if prev is not None and mark < prev:
            raise ValueError("dispatch milestones are out of order")
        if mark > event.canceled_at:
            raise ValueError("milestone occurs after cancellation")
        prev = mark


def _tonu_percent(event: TruckOrderEvent) -> Decimal:
    if event.arrived_at_shipper_at is not None:
        return Decimal("1.00")
    if event.en_route_at is not None:
        percent = Decimal("0.85")
    elif event.driver_assigned_at is not None:
        percent = Decimal("0.60")
    elif event.dispatch_sent_at is not None:
        percent = Decimal("0.35")
    else:
        percent = Decimal("0.00")

    if event.canceled_at >= event.appointment:
        return Decimal("1.00")
    hours_before = Decimal((event.appointment - event.canceled_at).total_seconds()) / Decimal(3600)
    if hours_before < Decimal("2") and percent < Decimal("0.90"):
        return Decimal("0.90")
    return percent


def _deadhead_charge(miles: Decimal, rate: Decimal) -> Decimal:
    if miles <= 0:
        return Decimal("0.00")
    rounded_miles = miles.to_integral_value(rounding="ROUND_CEILING")
    return (rounded_miles * rate).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_truck_order_not_used_fee(
    event: TruckOrderEvent, terms: TonuTerms = TonuTerms()
) -> Decimal:
    """Return the TONU fee in dollars.

    >>> from datetime import datetime
    >>> event = TruckOrderEvent(
    ...     appointment=datetime(2026, 5, 1, 10),
    ...     canceled_at=datetime(2026, 5, 1, 9),
    ...     dispatch_sent_at=datetime(2026, 5, 1, 8),
    ... )
    >>> calculate_truck_order_not_used_fee(event)
    Decimal('225.00')
    """
    _validate(event, terms)
    if event.loaded:
        return Decimal("0.00")
    if not event.truck_assigned:
        return Decimal("0.00")

    percent = _tonu_percent(event)
    deadhead = _deadhead_charge(event.deadhead_miles, terms.deadhead_rate)
    base = (terms.full_tonu * percent).quantize(CENT, rounding=ROUND_HALF_UP)
    if percent > 0 and base < terms.minimum_tonu:
        base = terms.minimum_tonu.quantize(CENT, rounding=ROUND_HALF_UP)

    if not terms.stack_deadhead_with_tonu:
        return max(base, deadhead).quantize(CENT, rounding=ROUND_HALF_UP)

    total = base + deadhead
    cap = terms.full_tonu + deadhead
    if total > cap:
        total = cap
    return total.quantize(CENT, rounding=ROUND_HALF_UP)
