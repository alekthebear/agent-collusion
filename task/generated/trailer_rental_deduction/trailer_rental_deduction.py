"""Trailer rental deductions owed by an owner-operator.

Tidewater sometimes rents company trailers to owner-operators and deducts the rental
from settlement. The rental desk records one continuous rental period for a trip or
for a week of local work. Billing follows these rules:

- Rental time is measured from ``picked_up`` to ``returned``; a return before pickup
  is invalid.
- Rentals of 6 hours or less are waived as yard turns and owe nothing.
- Time after the 6-hour waiver is billed by started day for the first 6 days.
- Once a rental reaches 7 billable days, it converts to week-based pricing: each full
  7-day block is billed at the weekly rate and any remainder is prorated by day at
  ``weekly_rate / 7``.
- Weekly proration is rounded half up to cents.
- If utilization is high enough, all rental is waived: at least 2 loaded moves and
  at least 1,000 loaded miles during the rental period.
- If utilization is moderate, one billable day is waived after pricing, but never
  below zero: at least 1 loaded move and at least 500 loaded miles.
- Refrigerated trailers add a daily reefer surcharge for each charged day unless the
  rental is fully waived for high utilization.
- A damage hold, when present, is added after all other calculations and is not waived.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
YARD_TURN_FREE_HOURS = 6
DAILY_RATE = Decimal("28.00")
WEEKLY_RATE = Decimal("175.00")
REEFER_DAILY_SURCHARGE = Decimal("9.50")


@dataclass(frozen=True)
class RentalPeriod:
    picked_up: datetime
    returned: datetime
    trailer_type: str = "dry"


@dataclass(frozen=True)
class Utilization:
    loaded_moves: int = 0
    loaded_miles: int = 0


@dataclass(frozen=True)
class RentalTerms:
    daily_rate: Decimal = DAILY_RATE
    weekly_rate: Decimal = WEEKLY_RATE
    reefer_daily_surcharge: Decimal = REEFER_DAILY_SURCHARGE
    damage_hold: Decimal = Decimal("0.00")


def _validate(period: RentalPeriod, utilization: Utilization, terms: RentalTerms) -> None:
    if period.returned < period.picked_up:
        raise ValueError("returned is before picked_up")
    if period.trailer_type not in {"dry", "reefer"}:
        raise ValueError("trailer_type must be 'dry' or 'reefer'")
    if utilization.loaded_moves < 0 or utilization.loaded_miles < 0:
        raise ValueError("utilization cannot be negative")
    if terms.damage_hold < Decimal("0.00"):
        raise ValueError("damage_hold cannot be negative")


def _billable_days(period: RentalPeriod) -> int:
    duration = period.returned - period.picked_up
    if duration <= timedelta(hours=YARD_TURN_FREE_HOURS):
        return 0
    extra = duration - timedelta(hours=YARD_TURN_FREE_HOURS)
    days = extra.total_seconds() / 86400
    whole = int(days)
    return whole if days == whole else whole + 1


def _high_utilization(utilization: Utilization) -> bool:
    return utilization.loaded_moves >= 2 and utilization.loaded_miles >= 1000


def _moderate_utilization(utilization: Utilization) -> bool:
    return utilization.loaded_moves >= 1 and utilization.loaded_miles >= 500


def _rental_amount_for_days(days: int, terms: RentalTerms) -> Decimal:
    if days <= 0:
        return Decimal("0.00")
    if days < 7:
        return terms.daily_rate * days
    weeks, remainder = divmod(days, 7)
    remainder_amount = (terms.weekly_rate * Decimal(remainder) / Decimal(7)).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    return terms.weekly_rate * weeks + remainder_amount


def calculate_trailer_rental_deduction(
    period: RentalPeriod,
    utilization: Utilization = Utilization(),
    terms: RentalTerms = RentalTerms(),
) -> Decimal:
    """Settlement deduction for one trailer rental period."""
    _validate(period, utilization, terms)
    days = _billable_days(period)
    if _high_utilization(utilization):
        return terms.damage_hold.quantize(CENT, rounding=ROUND_HALF_UP)

    charged_days = days
    if _moderate_utilization(utilization) and charged_days > 0:
        charged_days -= 1

    amount = _rental_amount_for_days(charged_days, terms)
    if period.trailer_type == "reefer" and charged_days > 0:
        amount += terms.reefer_daily_surcharge * charged_days
    amount += terms.damage_hold
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)
