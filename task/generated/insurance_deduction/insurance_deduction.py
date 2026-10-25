"""Insurance deductions withheld from a driver's settlement for enrolled coverages.

Tidewater settles occupational accident, physical damage, and cargo buy-up coverage
through payroll deduction. Each coverage has a weekly contribution, but settlements can
cover partial policy weeks at the start or end of an enrollment. We therefore prorate by
covered days inside the settlement period using a 7-day week. Amounts are rounded half-up
to the cent after proration per coverage, then totaled.

Business rules implemented here:
- Only enrolled coverages are billed.
- A coverage contributes only for overlap between its effective dates and the settlement
  period, inclusive of both start and end dates.
- Coverage with zero or negative weekly contribution is ignored.
- Occupational accident has a one-day waiting period at the start of a new enrollment;
  same-day settlements on the effective date do not bill it.
- Physical damage is not deducted when the truck is marked company-owned.
- Cargo buy-up is waived for hazmat-only operations when the insured value is at or below
  100,000.00.
- If the prorated subtotal for all billed coverages is under 5.00, the deduction is waived.
- If the driver terminates during the settlement period, no deduction is taken for days
  after the termination date.
- The total deduction is capped at 125.00 per settlement.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
MINIMUM_DEDUCTION = Decimal("5.00")
MAX_SETTLEMENT_DEDUCTION = Decimal("125.00")
HAZMAT_WAIVER_LIMIT = Decimal("100000.00")


@dataclass(frozen=True)
class CoverageElection:
    occupational_accident: bool = False
    physical_damage: bool = False
    cargo_buyup: bool = False


@dataclass(frozen=True)
class ContributionSchedule:
    occupational_accident_weekly: Decimal = Decimal("32.50")
    physical_damage_weekly: Decimal = Decimal("18.75")
    cargo_buyup_weekly: Decimal = Decimal("11.20")


@dataclass(frozen=True)
class InsuranceContext:
    settlement_start: date
    settlement_end: date
    enrollment_start: date
    enrollment_end: date | None = None
    termination_date: date | None = None
    truck_company_owned: bool = False
    hazmat_only: bool = False
    insured_value: Decimal = Decimal("0.00")


def _validate(ctx: InsuranceContext) -> None:
    if ctx.settlement_end < ctx.settlement_start:
        raise ValueError("settlement_end is before settlement_start")
    if ctx.enrollment_end is not None and ctx.enrollment_end < ctx.enrollment_start:
        raise ValueError("enrollment_end is before enrollment_start")
    if ctx.termination_date is not None and ctx.termination_date < ctx.enrollment_start:
        raise ValueError("termination_date is before enrollment_start")
    if ctx.insured_value < 0:
        raise ValueError("insured_value cannot be negative")


def _overlap_days(start: date, end: date, ctx: InsuranceContext) -> int:
    covered_start = max(start, ctx.settlement_start)
    covered_end = min(ctx.settlement_end, end)
    if ctx.enrollment_end is not None:
        covered_end = min(covered_end, ctx.enrollment_end)
    if ctx.termination_date is not None:
        covered_end = min(covered_end, ctx.termination_date)
    if covered_end < covered_start:
        return 0
    return (covered_end - covered_start).days + 1


def _prorated_amount(weekly_rate: Decimal, days: int) -> Decimal:
    if weekly_rate <= 0 or days <= 0:
        return Decimal("0.00")
    return (weekly_rate * Decimal(days) / Decimal(7)).quantize(CENT, rounding=ROUND_HALF_UP)


def _occupational_accident_days(ctx: InsuranceContext) -> int:
    billed_start = ctx.enrollment_start + timedelta(days=1)
    return _overlap_days(billed_start, date.max, ctx)


def _physical_damage_days(ctx: InsuranceContext) -> int:
    if ctx.truck_company_owned:
        return 0
    return _overlap_days(ctx.enrollment_start, date.max, ctx)


def _cargo_buyup_days(ctx: InsuranceContext) -> int:
    if ctx.hazmat_only and ctx.insured_value <= HAZMAT_WAIVER_LIMIT:
        return 0
    return _overlap_days(ctx.enrollment_start, date.max, ctx)


def calculate_insurance_deduction(
    elections: CoverageElection,
    ctx: InsuranceContext,
    schedule: ContributionSchedule = ContributionSchedule(),
) -> Decimal:
    """Insurance deduction for one settlement, rounded to the cent.

    Each elected coverage contributes its prorated share of the weekly amount for covered
    days inside the settlement period. The combined deduction may be waived for very small
    totals and is capped per settlement.
    """
    _validate(ctx)
    total = Decimal("0.00")

    if elections.occupational_accident:
        total += _prorated_amount(
            schedule.occupational_accident_weekly, _occupational_accident_days(ctx)
        )
    if elections.physical_damage:
        total += _prorated_amount(
            schedule.physical_damage_weekly, _physical_damage_days(ctx)
        )
    if elections.cargo_buyup:
        total += _prorated_amount(schedule.cargo_buyup_weekly, _cargo_buyup_days(ctx))

    if total < MINIMUM_DEDUCTION:
        return Decimal("0.00")
    if total > MAX_SETTLEMENT_DEDUCTION:
        return MAX_SETTLEMENT_DEDUCTION
    return total.quantize(CENT, rounding=ROUND_HALF_UP)
