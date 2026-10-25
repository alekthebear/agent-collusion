"""Driver payroll from payable miles under Tidewater's linehaul settlement rules.

This module computes one payroll line for mileage pay. Payroll starts from payable
miles after dispatch and billing adjustments. Solo drivers are paid all miles at
their mileage rate. Team loads split miles evenly by policy; if the load has an odd
number of miles, the extra mile is assigned to the first seat. Training trips are a
special case: a trainer is paid all payable miles at the trainer rate and the trainee
receives a flat training stipend instead of mileage.

Guaranteed minimums apply per driver only on dispatched work days. A guarantee is
met by adding a shortfall after mileage pay and bonuses, but flat training stipends do
not count toward satisfying the guarantee. Loads under 50 payable miles are yard or
shuttle moves and never receive a guarantee. Canadian cross-border loads pay a fixed
premium per driver. Final amounts are rounded to the nearest cent using half-up
rounding.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
SHORT_HAUL_MILES = 50
DEFAULT_CROSS_BORDER_PREMIUM = Decimal("15.00")
DEFAULT_TRAINEE_STIPEND = Decimal("75.00")


@dataclass(frozen=True)
class DriverPayProfile:
    mileage_rate: Decimal
    guaranteed_daily_minimum: Decimal = Decimal("0.00")


@dataclass(frozen=True)
class MileageTrip:
    payable_miles: int
    dispatched_days: int = 1
    is_team: bool = False
    is_training: bool = False
    crosses_canada: bool = False
    trainee_stipend: Decimal = DEFAULT_TRAINEE_STIPEND
    cross_border_premium: Decimal = DEFAULT_CROSS_BORDER_PREMIUM


@dataclass(frozen=True)
class PayrollBreakdown:
    primary_total: Decimal
    secondary_total: Decimal
    primary_miles: int
    secondary_miles: int
    primary_guarantee: Decimal
    secondary_guarantee: Decimal


def _money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate(trip: MileageTrip, primary: DriverPayProfile, secondary: DriverPayProfile | None) -> None:
    if trip.payable_miles < 0:
        raise ValueError("payable_miles cannot be negative")
    if trip.dispatched_days < 0:
        raise ValueError("dispatched_days cannot be negative")
    if trip.is_team and secondary is None:
        raise ValueError("secondary driver is required for team trips")
    if not trip.is_team and secondary is not None and not trip.is_training:
        raise ValueError("secondary driver only allowed on team or training trips")
    if trip.is_training and secondary is None:
        raise ValueError("trainee profile is required for training trips")


def _split_team_miles(payable_miles: int) -> tuple[int, int]:
    first = payable_miles // 2 + payable_miles % 2
    return first, payable_miles // 2


def _guarantee_shortfall(base_for_guarantee: Decimal, trip: MileageTrip, profile: DriverPayProfile) -> Decimal:
    if trip.payable_miles < SHORT_HAUL_MILES or trip.dispatched_days == 0:
        return Decimal("0.00")
    required = profile.guaranteed_daily_minimum * trip.dispatched_days
    if base_for_guarantee >= required:
        return Decimal("0.00")
    return _money(required - base_for_guarantee)


def calculate_mileage_payroll(
    trip: MileageTrip,
    primary: DriverPayProfile,
    secondary: DriverPayProfile | None = None,
) -> PayrollBreakdown:
    """Compute per-driver payroll totals for one mileage trip.

    The returned totals include mileage pay, any cross-border premium, and any
    guarantee shortfall. On training trips, the secondary driver's total is only the
    trainee stipend plus premium; the stipend does not count toward the guarantee.
    """
    _validate(trip, primary, secondary)

    if trip.is_training:
        primary_miles = trip.payable_miles
        secondary_miles = 0
    elif trip.is_team:
        primary_miles, secondary_miles = _split_team_miles(trip.payable_miles)
    else:
        primary_miles, secondary_miles = trip.payable_miles, 0

    premium = trip.cross_border_premium if trip.crosses_canada else Decimal("0.00")

    primary_mileage = _money(Decimal(primary_miles) * primary.mileage_rate)
    if trip.is_training:
        secondary_mileage = Decimal("0.00")
        secondary_flat = _money(trip.trainee_stipend)
    else:
        secondary_mileage = _money(Decimal(secondary_miles) * secondary.mileage_rate) if secondary else Decimal("0.00")
        secondary_flat = Decimal("0.00")

    primary_base = primary_mileage + premium
    secondary_base = secondary_mileage + premium

    primary_guarantee = _guarantee_shortfall(primary_base, trip, primary)
    if secondary is None:
        secondary_guarantee = Decimal("0.00")
    elif trip.is_training:
        secondary_guarantee = _guarantee_shortfall(premium, trip, secondary)
    else:
        secondary_guarantee = _guarantee_shortfall(secondary_base, trip, secondary)

    primary_total = _money(primary_base + primary_guarantee)
    secondary_total = _money(secondary_base + secondary_flat + secondary_guarantee)

    return PayrollBreakdown(
        primary_total=primary_total,
        secondary_total=secondary_total,
        primary_miles=primary_miles,
        secondary_miles=secondary_miles,
        primary_guarantee=primary_guarantee,
        secondary_guarantee=secondary_guarantee,
    )
