"""Chassis split charges when a driver must source or return equipment away from the
terminal.

A chassis split occurs when the import or export move cannot use the chassis at the
marine terminal and the driver must perform extra dray between a yard and the port.
Tidewater's standard customer rule bills a flat split fee plus mileage for the extra
positioning. Some moves earn a discount when the same visit completes a dual
transaction, while urgent after-hours yard pulls add a surcharge. Very short local
repositions are absorbed into the base fee and do not bill mileage.
"""

from dataclasses import dataclass
from datetime import datetime, time
from decimal import ROUND_HALF_UP, Decimal

BASE_SPLIT_FEE = Decimal("95.00")
MILEAGE_RATE = Decimal("4.25")
INCLUDED_MILES = Decimal("5")
AFTER_HOURS_SURCHARGE = Decimal("35.00")
DUAL_TRANSACTION_CREDIT = Decimal("25.00")
MINIMUM_BILLABLE = Decimal("65.00")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class SplitMove:
    """Facts needed to rate one chassis split event."""

    terminal_to_yard_miles: Decimal
    completed_at: datetime
    dual_transaction: bool = False
    customer_flat_fee: Decimal | None = None
    customer_mileage_rate: Decimal | None = None
    waive_mileage: bool = False


@dataclass(frozen=True)
class SplitTerms:
    base_fee: Decimal = BASE_SPLIT_FEE
    mileage_rate: Decimal = MILEAGE_RATE
    included_miles: Decimal = INCLUDED_MILES
    after_hours_surcharge: Decimal = AFTER_HOURS_SURCHARGE
    dual_transaction_credit: Decimal = DUAL_TRANSACTION_CREDIT
    minimum_billable: Decimal = MINIMUM_BILLABLE


def _validate(move: SplitMove, terms: SplitTerms) -> None:
    if move.terminal_to_yard_miles < 0:
        raise ValueError("terminal_to_yard_miles cannot be negative")
    if (move.customer_flat_fee is not None and move.customer_flat_fee < 0) or (
        move.customer_mileage_rate is not None and move.customer_mileage_rate < 0
    ):
        raise ValueError("contractual fees cannot be negative")
    if terms.included_miles < 0 or terms.minimum_billable < 0:
        raise ValueError("terms cannot be negative")


def _is_after_hours(when: datetime) -> bool:
    t = when.time()
    return t < time(6, 0) or t >= time(18, 0) or when.weekday() >= 5


def _extra_miles(move: SplitMove, terms: SplitTerms) -> Decimal:
    if move.waive_mileage:
        return Decimal("0")
    miles = move.terminal_to_yard_miles * 2
    extra = miles - terms.included_miles
    if extra <= 0:
        return Decimal("0")
    return extra


def _round_money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_chassis_split_fee(
    move: SplitMove, terms: SplitTerms = SplitTerms()
) -> Decimal:
    """Rate one chassis split in dollars rounded to the cent.

    The charge starts with the contractual flat fee when present, otherwise the
    standard base fee. Round-trip dray miles between terminal and yard are used for
    mileage, with the first ``included_miles`` absorbed into the flat fee. Mileage
    can be waived by contract. A dual transaction receives a fixed credit, and any
    split completed after 18:00, before 06:00, or on a weekend adds the after-hours
    surcharge. The final amount cannot fall below ``minimum_billable``.
    """
    _validate(move, terms)

    base_fee = move.customer_flat_fee if move.customer_flat_fee is not None else terms.base_fee
    mileage_rate = (
        move.customer_mileage_rate if move.customer_mileage_rate is not None else terms.mileage_rate
    )

    amount = base_fee
    amount += _extra_miles(move, terms) * mileage_rate

    if move.dual_transaction:
        amount -= terms.dual_transaction_credit
    if _is_after_hours(move.completed_at):
        amount += terms.after_hours_surcharge

    amount = _round_money(amount)
    if amount < terms.minimum_billable:
        return terms.minimum_billable
    return amount
