"""Deadhead compensation for approved empty reposition miles.

Deadhead pay covers approved empty miles a driver runs to reach a pickup, reposition
between customer moves, or return equipment under a contract program. Tidewater's
standard rules are: a configurable number of free miles are not paid, then approved
miles are paid either per mile or as a flat dispatch amount. Flat pay applies only
when the paid miles meet a minimum threshold; otherwise mileage pay is used instead.

Miles are rounded down to the nearest whole mile before billing. Mileage pay is
rounded to the cent using half-up rounding. Contracts may cap a deadhead event at a
maximum payable amount. Negative miles and non-positive rates are rejected. In
addition, short canceled moves under 5 approved miles never pay, even if a flat
amount would otherwise apply.
"""

from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
WHOLE_MILE = Decimal("1")
DEFAULT_FREE_MILES = Decimal("25")
DEFAULT_MILE_RATE = Decimal("1.10")
DEFAULT_FLAT_AMOUNT = Decimal("75.00")
DEFAULT_FLAT_MIN_MILES = Decimal("80")
DEFAULT_EVENT_CAP = Decimal("250.00")


@dataclass(frozen=True)
class DeadheadMove:
    """Approved deadhead details for one payable event."""

    approved_miles: Decimal
    canceled: bool = False
    same_market: bool = False


@dataclass(frozen=True)
class DeadheadTerms:
    free_miles: Decimal = DEFAULT_FREE_MILES
    mile_rate: Decimal = DEFAULT_MILE_RATE
    flat_amount: Decimal = DEFAULT_FLAT_AMOUNT
    flat_min_miles: Decimal = DEFAULT_FLAT_MIN_MILES
    event_cap: Decimal | None = DEFAULT_EVENT_CAP


def _validate(move: DeadheadMove, terms: DeadheadTerms) -> None:
    if move.approved_miles < 0:
        raise ValueError(f"approved_miles {move.approved_miles} must be non-negative")
    if terms.free_miles < 0:
        raise ValueError(f"free_miles {terms.free_miles} must be non-negative")
    if terms.mile_rate <= 0:
        raise ValueError(f"mile_rate {terms.mile_rate} must be positive")
    if terms.flat_amount <= 0:
        raise ValueError(f"flat_amount {terms.flat_amount} must be positive")
    if terms.flat_min_miles <= 0:
        raise ValueError(f"flat_min_miles {terms.flat_min_miles} must be positive")
    if terms.event_cap is not None and terms.event_cap <= 0:
        raise ValueError(f"event_cap {terms.event_cap} must be positive when provided")


def _rounded_miles(miles: Decimal) -> Decimal:
    return miles.quantize(WHOLE_MILE, rounding=ROUND_DOWN)


def _effective_free_miles(move: DeadheadMove, terms: DeadheadTerms) -> Decimal:
    free_miles = terms.free_miles
    if move.same_market:
        free_miles += Decimal("10")
    if move.canceled:
        free_miles += Decimal("15")
    return free_miles


def _paid_miles(move: DeadheadMove, terms: DeadheadTerms) -> Decimal:
    paid = _rounded_miles(move.approved_miles) - _effective_free_miles(move, terms)
    return paid if paid > 0 else Decimal("0")


def _mileage_amount(paid_miles: Decimal, terms: DeadheadTerms) -> Decimal:
    return (paid_miles * terms.mile_rate).quantize(CENT, rounding=ROUND_HALF_UP)


def _apply_cap(amount: Decimal, cap: Decimal | None) -> Decimal:
    if cap is not None and amount > cap:
        return cap
    return amount


def calculate_deadhead_pay(
    move: DeadheadMove, terms: DeadheadTerms = DeadheadTerms()
) -> Decimal:
    """Compute deadhead pay for one approved move.

    Approved miles are rounded down to a whole mile, reduced by free miles, then paid
    at the mileage rate. If paid miles meet or exceed ``flat_min_miles``, the greater
    of mileage pay and ``flat_amount`` is used. Canceled moves under 5 approved miles
    do not pay. The final amount is capped by ``event_cap`` when present.

    >>> calculate_deadhead_pay(DeadheadMove(approved_miles=Decimal("110")))
    Decimal('93.50')
    """
    _validate(move, terms)
    rounded_miles = _rounded_miles(move.approved_miles)
    if move.canceled and rounded_miles < Decimal("5"):
        return Decimal("0.00")
    paid_miles = _paid_miles(move, terms)
    if paid_miles == 0:
        return Decimal("0.00")
    mileage_pay = _mileage_amount(paid_miles, terms)
    amount = mileage_pay
    if paid_miles >= terms.flat_min_miles:
        amount = max(mileage_pay, terms.flat_amount)
    return _apply_cap(amount, terms.event_cap)
