"""Trailer spotting charges for drop-yard hostling and reposition work.

Spotting is billed when a yard hostler moves trailers between dock doors, staging rows,
and parking locations. Tidewater's shared rating rules are:

* Billing starts with a per-move rate based on hostler type.
* A minimum move charge applies whenever any work is performed, even if move count is low.
* Standby time is not billed until it exceeds included minutes tied to the hostler type.
* Billable standby is charged per started billing increment, using the contract increment
  length and hourly standby rate.
* On dedicated hostlers, the first move is treated as positioning and is not billed when
  there is standby time but no more than one move total.
* During overnight quiet hours, non-dedicated hostlers doing only one move with no billable
  standby are waived as a customer-service exception.
* The final amount is rounded half up to the cent.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
DEFAULT_INCREMENT_MINUTES = 15


@dataclass(frozen=True)
class SpottingWork:
    moved_at: datetime
    move_count: int
    standby: timedelta = timedelta(0)
    overnight_quiet_hours: bool = False


@dataclass(frozen=True)
class SpottingTerms:
    hostler_type: str = "shared"
    move_rate: Decimal = Decimal("32.50")
    standby_hourly_rate: Decimal = Decimal("68.00")
    minimum_charge: Decimal = Decimal("65.00")
    standby_included_minutes: int = 30
    billing_increment_minutes: int = DEFAULT_INCREMENT_MINUTES


def _validate(work: SpottingWork, terms: SpottingTerms) -> None:
    if work.move_count < 0:
        raise ValueError("move_count cannot be negative")
    if work.standby < timedelta(0):
        raise ValueError("standby cannot be negative")
    if terms.hostler_type not in {"shared", "dedicated", "contractor"}:
        raise ValueError(f"unsupported hostler_type {terms.hostler_type!r}")
    if terms.billing_increment_minutes <= 0:
        raise ValueError("billing_increment_minutes must be positive")
    if terms.standby_included_minutes < 0:
        raise ValueError("standby_included_minutes cannot be negative")


def _included_minutes(terms: SpottingTerms) -> int:
    if terms.hostler_type == "dedicated":
        return max(terms.standby_included_minutes, 45)
    if terms.hostler_type == "contractor":
        return min(terms.standby_included_minutes, 15)
    return terms.standby_included_minutes


def _billable_moves(work: SpottingWork, terms: SpottingTerms) -> int:
    if terms.hostler_type == "dedicated" and work.standby > timedelta(0) and work.move_count <= 1:
        return 0
    return work.move_count


def _billable_standby_increments(work: SpottingWork, terms: SpottingTerms) -> int:
    included = timedelta(minutes=_included_minutes(terms))
    extra = work.standby - included
    if extra <= timedelta(0):
        return 0
    minutes = extra.total_seconds() / 60
    whole, partial = divmod(minutes, terms.billing_increment_minutes)
    return int(whole) + (1 if partial else 0)


def _waived_for_quiet_hours(work: SpottingWork, terms: SpottingTerms, standby_increments: int) -> bool:
    return (
        work.overnight_quiet_hours
        and terms.hostler_type != "dedicated"
        and work.move_count == 1
        and standby_increments == 0
    )


def calculate_spotting_fee(
    work: SpottingWork, terms: SpottingTerms = SpottingTerms()
) -> Decimal:
    """Spotting charge for one yard service event.

    If there is no work at all (zero moves and no standby), the charge is zero. Otherwise,
    move charges and standby charges are added, then the contractual minimum is enforced
    unless the overnight single-move waiver applies.
    """
    _validate(work, terms)
    if work.move_count == 0 and work.standby == timedelta(0):
        return Decimal("0.00")

    standby_increments = _billable_standby_increments(work, terms)
    if _waived_for_quiet_hours(work, terms, standby_increments):
        return Decimal("0.00")

    billable_moves = _billable_moves(work, terms)
    move_charge = terms.move_rate * billable_moves
    standby_charge = (
        terms.standby_hourly_rate
        * Decimal(standby_increments * terms.billing_increment_minutes)
        / Decimal(60)
    )
    total = move_charge + standby_charge
    if total < terms.minimum_charge:
        total = terms.minimum_charge
    return total.quantize(CENT, rounding=ROUND_HALF_UP)
