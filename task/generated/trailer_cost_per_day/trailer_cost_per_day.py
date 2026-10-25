"""Trailer ownership or lease cost allocated to one operating day.

The rating service uses this when a lane analyst needs a daily trailer cost to turn
annual equipment expense into a per-day figure. The business rules are:
- Available days must be between 1 and 366 inclusive.
- Available days represent the days a trailer can be assigned to loads, so annual
  ownership expense is spread only across those days.
- Owned trailers depreciate on a straight-line basis from purchase price less salvage
  value over their useful life. Leased trailers do not depreciate.
- Financed owned trailers incur annual interest on the average outstanding principal
  for the year: opening balance plus closing balance, divided by two.
- Closing balance cannot go below zero and is reduced by scheduled principal paid
  during the year.
- Fixed annual expenses include registration, insurance, permits, and telematics.
- Refrigerated trailers add a reefer compliance surcharge of $1.75 per available day.
- Trailers older than 10 service years add a maintenance reserve of $2.40 per day;
  older than 15 service years use $4.10 per day instead.
- If the trailer is leased, annual lease cost replaces depreciation and financing.
- Final cost is rounded to the nearest cent using half-up rounding.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
REEFER_SURCHARGE_PER_DAY = Decimal("1.75")
OLDER_RESERVE = Decimal("2.40")
VERY_OLD_RESERVE = Decimal("4.10")


@dataclass(frozen=True)
class TrailerProfile:
    purchase_price: Decimal
    salvage_value: Decimal
    service_years: int
    useful_life_years: int
    refrigerated: bool = False
    leased: bool = False


@dataclass(frozen=True)
class FinancingTerms:
    opening_principal: Decimal = Decimal("0.00")
    annual_interest_rate: Decimal = Decimal("0.00")
    scheduled_principal_paid: Decimal = Decimal("0.00")
    annual_lease_cost: Decimal = Decimal("0.00")


@dataclass(frozen=True)
class FixedExpenses:
    registration: Decimal = Decimal("0.00")
    insurance: Decimal = Decimal("0.00")
    permits: Decimal = Decimal("0.00")
    telematics: Decimal = Decimal("0.00")
    available_days: int = 365


def _validate(profile: TrailerProfile, financing: FinancingTerms, fixed: FixedExpenses) -> None:
    if not 1 <= fixed.available_days <= 366:
        raise ValueError("available_days must be between 1 and 366")
    if profile.useful_life_years <= 0:
        raise ValueError("useful_life_years must be positive")
    if profile.service_years < 0:
        raise ValueError("service_years cannot be negative")
    if profile.salvage_value > profile.purchase_price:
        raise ValueError("salvage_value cannot exceed purchase_price")
    if financing.annual_interest_rate < 0:
        raise ValueError("annual_interest_rate cannot be negative")
    if financing.opening_principal < 0 or financing.scheduled_principal_paid < 0:
        raise ValueError("principal amounts cannot be negative")
    if financing.annual_lease_cost < 0:
        raise ValueError("annual_lease_cost cannot be negative")


def _annual_fixed_expenses(fixed: FixedExpenses) -> Decimal:
    return fixed.registration + fixed.insurance + fixed.permits + fixed.telematics


def _annual_depreciation(profile: TrailerProfile) -> Decimal:
    if profile.leased:
        return Decimal("0.00")
    depreciable_basis = profile.purchase_price - profile.salvage_value
    return depreciable_basis / Decimal(profile.useful_life_years)


def _annual_financing(financing: FinancingTerms, profile: TrailerProfile) -> Decimal:
    if profile.leased or financing.opening_principal == 0 or financing.annual_interest_rate == 0:
        return Decimal("0.00")
    closing = financing.opening_principal - financing.scheduled_principal_paid
    if closing < 0:
        closing = Decimal("0.00")
    average_principal = (financing.opening_principal + closing) / Decimal("2")
    return average_principal * financing.annual_interest_rate


def _age_reserve_per_day(service_years: int) -> Decimal:
    if service_years > 15:
        return VERY_OLD_RESERVE
    if service_years > 10:
        return OLDER_RESERVE
    return Decimal("0.00")


def calculate_trailer_cost_per_day(
    profile: TrailerProfile,
    financing: FinancingTerms = FinancingTerms(),
    fixed: FixedExpenses = FixedExpenses(),
) -> Decimal:
    """Return the trailer's allocated cost per available day in dollars.

    Ownership cost combines annual depreciation, annual financing cost, annual fixed
    expenses, and age or reefer daily surcharges. Leased trailers use annual lease
    cost instead of depreciation and financing.
    """
    _validate(profile, financing, fixed)
    annual_base = _annual_fixed_expenses(fixed)
    if profile.leased:
        annual_base += financing.annual_lease_cost
    else:
        annual_base += _annual_depreciation(profile) + _annual_financing(financing, profile)
    daily = annual_base / Decimal(fixed.available_days)
    daily += _age_reserve_per_day(profile.service_years)
    if profile.refrigerated:
        daily += REEFER_SURCHARGE_PER_DAY
    return daily.quantize(CENT, rounding=ROUND_HALF_UP)
