"""Trailer pool balance for one location over a settlement window.

A trailer pool location starts with an on-hand trailer count, then moves through
inbound and outbound events. Operations compares the ending on-hand count to a
contract target pool. A positive balance means surplus trailers above target; a
negative balance means a deficit below target.

Business rules:
- Starting inventory, target level, and all event quantities must be whole trailers
  and cannot be negative.
- Outbound movements reduce inventory. Inbound movements increase inventory.
- "yard_check" adjustments may be positive or negative and represent a physical
  recount correction.
- A location cannot end below zero physical trailers. If movements would drive the
  count negative, the ending inventory is floored at zero before balance is judged.
- Shortages are charged per trailer below target at the shortage rate.
- Surplus trailers earn no credit until they exceed the free surplus allowance.
  Surplus above that allowance is credited per trailer at the surplus rate.
- If ending inventory lands inside the deadband around target, no debit or credit is
  produced even if the raw count is slightly above or below target.
- Money is rounded to the cent with half-up rounding.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
DEFAULT_SHORTAGE_RATE = Decimal("18.50")
DEFAULT_SURPLUS_RATE = Decimal("4.25")
DEFAULT_DEADBAND = 1
DEFAULT_FREE_SURPLUS = 2


@dataclass(frozen=True)
class PoolEvent:
    kind: str
    quantity: int


@dataclass(frozen=True)
class PoolTerms:
    target_level: int
    shortage_rate: Decimal = DEFAULT_SHORTAGE_RATE
    surplus_rate: Decimal = DEFAULT_SURPLUS_RATE
    deadband: int = DEFAULT_DEADBAND
    free_surplus: int = DEFAULT_FREE_SURPLUS


@dataclass(frozen=True)
class PoolBalance:
    ending_inventory: int
    variance_to_target: int
    shortage_trailers: int
    surplus_trailers: int
    charge: Decimal
    credit: Decimal
    net_balance: Decimal


def _validate_inputs(starting_inventory: int, events: list[PoolEvent], terms: PoolTerms) -> None:
    if starting_inventory < 0:
        raise ValueError("starting_inventory cannot be negative")
    if terms.target_level < 0:
        raise ValueError("target_level cannot be negative")
    if terms.deadband < 0:
        raise ValueError("deadband cannot be negative")
    if terms.free_surplus < 0:
        raise ValueError("free_surplus cannot be negative")
    for rate_name, rate in (("shortage_rate", terms.shortage_rate), ("surplus_rate", terms.surplus_rate)):
        if rate < 0:
            raise ValueError(f"{rate_name} cannot be negative")
    for event in events:
        if event.kind not in {"inbound", "outbound", "yard_check"}:
            raise ValueError(f"unknown event kind: {event.kind}")
        if event.kind != "yard_check" and event.quantity < 0:
            raise ValueError(f"{event.kind} quantity cannot be negative")


def _apply_event(inventory: int, event: PoolEvent) -> int:
    if event.kind == "inbound":
        return inventory + event.quantity
    if event.kind == "outbound":
        return inventory - event.quantity
    return inventory + event.quantity


def _money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _variance_to_target(ending_inventory: int, target_level: int, deadband: int) -> int:
    variance = ending_inventory - target_level
    if abs(variance) <= deadband:
        return 0
    return variance


def calculate_trailer_pool_balance(
    starting_inventory: int,
    events: list[PoolEvent],
    terms: PoolTerms,
) -> PoolBalance:
    """Return ending inventory and surplus/deficit settlement for one location.

    >>> terms = PoolTerms(target_level=10)
    >>> events = [PoolEvent("inbound", 3), PoolEvent("outbound", 1)]
    >>> calculate_trailer_pool_balance(8, events, terms).net_balance
    Decimal('0.00')
    """
    _validate_inputs(starting_inventory, events, terms)

    inventory = starting_inventory
    for event in events:
        inventory = _apply_event(inventory, event)
    ending_inventory = max(inventory, 0)

    variance = _variance_to_target(ending_inventory, terms.target_level, terms.deadband)
    shortage_trailers = 0
    surplus_trailers = 0
    charge = Decimal("0.00")
    credit = Decimal("0.00")

    if variance < 0:
        shortage_trailers = abs(variance)
        charge = _money(Decimal(shortage_trailers) * terms.shortage_rate)
    elif variance > 0:
        billable_surplus = max(variance - terms.free_surplus, 0)
        surplus_trailers = billable_surplus
        credit = _money(Decimal(billable_surplus) * terms.surplus_rate)

    net_balance = charge - credit
    return PoolBalance(
        ending_inventory=ending_inventory,
        variance_to_target=variance,
        shortage_trailers=shortage_trailers,
        surplus_trailers=surplus_trailers,
        charge=charge,
        credit=credit,
        net_balance=_money(net_balance),
    )
