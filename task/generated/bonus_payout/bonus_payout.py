"""Driver performance bonus payouts for settled payroll periods.

A payout is computed from miles, on-time service, safety events, and customer
claims. Only eligible periods can earn a bonus. The calculation follows these
business rules:
- Fewer than 2,000 eligible miles earns no bonus.
- A base cents-per-mile rate comes from the on-time tier table:
  under 96.0% => ineligible, 96.0% to 97.99% => 2.5 cpm,
  98.0% to 98.99% => 4.0 cpm, 99.0% and above => 5.5 cpm.
- Any preventable accident makes the period ineligible.
- HOS violations reduce the base by 25% each, capped at a 50% reduction.
- Customer claims reduce payout only by the amount above a 250.00 deductible on
  each claim; claims at or below the deductible do not reduce the payout.
- Reefer and hazmat endorsements each add a 10% premium to the reduced base
  payout.
- Team drivers receive a 15% premium after endorsement premiums.
- The final payout is floored at 0.00 and capped at 500.00, rounded half up to
  cents.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
MIN_MILES = 2000
PAYOUT_CAP = Decimal("500.00")
CLAIM_DEDUCTIBLE = Decimal("250.00")


@dataclass(frozen=True)
class PerformanceMetrics:
    eligible_miles: int
    on_time_ratio: Decimal
    hos_violations: int = 0
    preventable_accidents: int = 0
    customer_claims: tuple[Decimal, ...] = ()


@dataclass(frozen=True)
class BonusProfile:
    reefer_certified: bool = False
    hazmat_certified: bool = False
    team_driver: bool = False
    payout_cap: Decimal = PAYOUT_CAP


def _validate(metrics: PerformanceMetrics, profile: BonusProfile) -> None:
    if metrics.eligible_miles < 0:
        raise ValueError("eligible_miles cannot be negative")
    if metrics.hos_violations < 0 or metrics.preventable_accidents < 0:
        raise ValueError("event counts cannot be negative")
    if metrics.on_time_ratio < Decimal("0") or metrics.on_time_ratio > Decimal("100"):
        raise ValueError("on_time_ratio must be between 0 and 100")
    if any(claim < Decimal("0.00") for claim in metrics.customer_claims):
        raise ValueError("customer claims cannot be negative")
    if profile.payout_cap < Decimal("0.00"):
        raise ValueError("payout_cap cannot be negative")


def _base_cents_per_mile(on_time_ratio: Decimal) -> Decimal:
    if on_time_ratio < Decimal("96.0"):
        return Decimal("0.00")
    if on_time_ratio < Decimal("98.0"):
        return Decimal("0.025")
    if on_time_ratio < Decimal("99.0"):
        return Decimal("0.040")
    return Decimal("0.055")


def _violation_multiplier(hos_violations: int) -> Decimal:
    reduction = min(hos_violations, 2) * Decimal("0.25")
    return Decimal("1.00") - reduction


def _claim_deduction(customer_claims: tuple[Decimal, ...]) -> Decimal:
    deduction = Decimal("0.00")
    for claim in customer_claims:
        if claim > CLAIM_DEDUCTIBLE:
            deduction += claim - CLAIM_DEDUCTIBLE
    return deduction


def _premium_multiplier(profile: BonusProfile) -> Decimal:
    multiplier = Decimal("1.00")
    if profile.reefer_certified:
        multiplier += Decimal("0.10")
    if profile.hazmat_certified:
        multiplier += Decimal("0.10")
    if profile.team_driver:
        multiplier *= Decimal("1.15")
    return multiplier



def _apply_bounds(amount: Decimal, cap: Decimal) -> Decimal:
    if amount <= Decimal("0.00"):
        return Decimal("0.00")
    if amount > cap:
        return cap
    return amount


def calculate_bonus_payout(
    metrics: PerformanceMetrics, profile: BonusProfile = BonusProfile()
) -> Decimal:
    """Return payroll bonus payout for one settled period.

    >>> calculate_bonus_payout(PerformanceMetrics(2500, Decimal("98.0")))
    Decimal('100.00')
    """
    _validate(metrics, profile)
    if metrics.eligible_miles < MIN_MILES:
        return Decimal("0.00")
    if metrics.preventable_accidents > 0:
        return Decimal("0.00")

    cpm = _base_cents_per_mile(metrics.on_time_ratio)
    if cpm == Decimal("0.00"):
        return Decimal("0.00")

    base = Decimal(metrics.eligible_miles) * cpm
    reduced = base * _violation_multiplier(metrics.hos_violations)
    with_premiums = reduced * _premium_multiplier(profile)
    net = with_premiums - _claim_deduction(metrics.customer_claims)
    bounded = _apply_bounds(net, profile.payout_cap)
    return bounded.quantize(CENT, rounding=ROUND_HALF_UP)
