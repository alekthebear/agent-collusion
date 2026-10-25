"""Maintenance-fund contributions withheld from owner-operator settlements.

The maintenance fund is an internal escrow used to smooth large repair events. A lease
may fund it three different ways: by loaded mile, as a percentage of linehaul revenue,
or as a flat amount per settlement period. Contributions are calculated per settlement
and rounded to the cent.

Business rules used by Tidewater Freight:
- Exactly one funding basis applies: mileage, revenue percentage, or flat periodic.
- Negative miles or revenue are invalid.
- Loaded miles under 50 do not fund the account on mileage plans.
- Mileage plans charge a per-mile rate only on loaded miles, then add a remote-area
  surcharge of $7.50 when loaded miles exceed 1,200 in a settlement.
- Revenue plans apply only to linehaul revenue, excluding FSC and accessorials. If the
  linehaul revenue is below $300.00, no contribution is withheld.
- Flat periodic plans skip the contribution when the operator is on approved home time
  for 14 or more days in the settlement.
- A settlement may waive up to one missed scheduled contribution per calendar quarter;
  if waived, the contribution is zero.
- The contribution may not exceed the remaining account room below the account cap.
  If the account is already at or above the cap, no contribution is taken.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
REMOTE_SURCHARGE = Decimal("7.50")
MILEAGE_MINIMUM = 50
REVENUE_MINIMUM = Decimal("300.00")
HOME_TIME_WAIVER_DAYS = 14


@dataclass(frozen=True)
class SettlementFacts:
    loaded_miles: int = 0
    linehaul_revenue: Decimal = Decimal("0.00")
    account_balance: Decimal = Decimal("0.00")
    account_cap: Decimal = Decimal("2000.00")
    home_time_days: int = 0
    waived_for_quarter: bool = False


@dataclass(frozen=True)
class MaintenanceFundTerms:
    per_loaded_mile: Decimal | None = None
    revenue_percent: Decimal | None = None
    flat_amount: Decimal | None = None


def _validate_terms(terms: MaintenanceFundTerms) -> None:
    configured = [
        terms.per_loaded_mile is not None,
        terms.revenue_percent is not None,
        terms.flat_amount is not None,
    ]
    if sum(configured) != 1:
        raise ValueError("exactly one funding basis must be configured")
    if terms.per_loaded_mile is not None and terms.per_loaded_mile < 0:
        raise ValueError("per_loaded_mile cannot be negative")
    if terms.revenue_percent is not None and terms.revenue_percent < 0:
        raise ValueError("revenue_percent cannot be negative")
    if terms.flat_amount is not None and terms.flat_amount < 0:
        raise ValueError("flat_amount cannot be negative")


def _validate_facts(facts: SettlementFacts) -> None:
    if facts.loaded_miles < 0:
        raise ValueError("loaded_miles cannot be negative")
    if facts.linehaul_revenue < 0:
        raise ValueError("linehaul_revenue cannot be negative")
    if facts.account_balance < 0:
        raise ValueError("account_balance cannot be negative")
    if facts.account_cap < 0:
        raise ValueError("account_cap cannot be negative")
    if facts.home_time_days < 0:
        raise ValueError("home_time_days cannot be negative")


def _raw_contribution(facts: SettlementFacts, terms: MaintenanceFundTerms) -> Decimal:
    if facts.waived_for_quarter:
        return Decimal("0.00")
    if terms.per_loaded_mile is not None:
        if facts.loaded_miles < MILEAGE_MINIMUM:
            return Decimal("0.00")
        amount = Decimal(facts.loaded_miles) * terms.per_loaded_mile
        if facts.loaded_miles > 1200:
            amount += REMOTE_SURCHARGE
        return amount
    if terms.revenue_percent is not None:
        if facts.linehaul_revenue < REVENUE_MINIMUM:
            return Decimal("0.00")
        return facts.linehaul_revenue * terms.revenue_percent / Decimal("100")
    if facts.home_time_days >= HOME_TIME_WAIVER_DAYS:
        return Decimal("0.00")
    return terms.flat_amount or Decimal("0.00")


def _apply_cap(amount: Decimal, balance: Decimal, cap: Decimal) -> Decimal:
    remaining = cap - balance
    if remaining <= 0:
        return Decimal("0.00")
    if amount > remaining:
        return remaining
    return amount


def calculate_maintenance_fund_contribution(
    facts: SettlementFacts,
    terms: MaintenanceFundTerms,
) -> Decimal:
    """Return the settlement maintenance-fund deduction in dollars.

    The deduction is computed from the configured funding basis, rounded half up to the
    cent, then limited so the resulting account balance does not exceed the cap.
    """
    _validate_facts(facts)
    _validate_terms(terms)
    amount = _raw_contribution(facts, terms).quantize(CENT, rounding=ROUND_HALF_UP)
    return _apply_cap(amount, facts.account_balance, facts.account_cap).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
