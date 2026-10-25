"""Random drug-testing pool requirements for active CDL drivers.

Safety and compliance teams size each selection period from the count of active,
covered drivers and the annual random drug-testing rate in effect for that year.
The period requirement is the annual target spread across the remaining regular
periods in the calendar year so the carrier can catch up if earlier periods ran
short.

Business rules implemented here:
- Only active, covered CDL drivers count in the pool.
- Drivers on long-term leave of 31 days or more are excluded for the period.
- Owner-operators leased on under the carrier's authority are included.
- If the annual rate is zero, the requirement is zero.
- Quarterly programs divide the remaining annual obligation by remaining quarters,
  monthly programs by remaining months.
- The annual target is population multiplied by the annual rate, rounded to a
  whole driver using half-up rounding.
- The current period's requirement is the remaining annual target minus prior
  selections already completed, divided by periods remaining, then rounded up so
  fractional drivers are not deferred.
- The result cannot be negative and cannot exceed the count of eligible drivers.
"""

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal


WHOLE = Decimal("1")


@dataclass(frozen=True)
class DriverPool:
    active_cdl_drivers: int
    noncovered_drivers: int = 0
    long_term_leave_drivers: int = 0
    leased_owner_operators: int = 0


@dataclass(frozen=True)
class TestingPeriod:
    annual_rate: Decimal
    cadence: str
    period_number: int
    prior_random_selections: int = 0


def _validate(pool: DriverPool, period: TestingPeriod) -> None:
    for name, value in (
        ("active_cdl_drivers", pool.active_cdl_drivers),
        ("noncovered_drivers", pool.noncovered_drivers),
        ("long_term_leave_drivers", pool.long_term_leave_drivers),
        ("leased_owner_operators", pool.leased_owner_operators),
        ("period_number", period.period_number),
        ("prior_random_selections", period.prior_random_selections),
    ):
        if value < 0:
            raise ValueError(f"{name} cannot be negative")
    if period.annual_rate < 0:
        raise ValueError("annual_rate cannot be negative")
    if period.cadence not in {"monthly", "quarterly"}:
        raise ValueError("cadence must be monthly or quarterly")
    max_period = 12 if period.cadence == "monthly" else 4
    if not 1 <= period.period_number <= max_period:
        raise ValueError(f"period_number must be between 1 and {max_period}")


def _eligible_driver_count(pool: DriverPool) -> int:
    eligible = pool.active_cdl_drivers - pool.noncovered_drivers - pool.long_term_leave_drivers
    eligible += pool.leased_owner_operators
    return max(eligible, 0)


def _periods_in_year(cadence: str) -> int:
    return 12 if cadence == "monthly" else 4


def _annual_target(eligible_drivers: int, annual_rate: Decimal) -> int:
    target = (Decimal(eligible_drivers) * annual_rate).quantize(WHOLE, rounding=ROUND_HALF_UP)
    return int(target)


def calculate_drug_testing_pool_requirement(
    pool: DriverPool, period: TestingPeriod
) -> int:
    """Required random drug-test selections for the current period.

    The function annualizes the eligible population, subtracts prior selections,
    allocates the remainder across the current and future periods in the year, and
    rounds up to a whole selection for the current period.
    """
    _validate(pool, period)
    eligible = _eligible_driver_count(pool)
    if eligible == 0 or period.annual_rate == 0:
        return 0

    annual_target = _annual_target(eligible, period.annual_rate)
    remaining = annual_target - period.prior_random_selections
    if remaining <= 0:
        return 0

    total_periods = _periods_in_year(period.cadence)
    periods_remaining = total_periods - period.period_number + 1
    per_period = (Decimal(remaining) / Decimal(periods_remaining)).quantize(
        WHOLE, rounding=ROUND_CEILING
    )
    required = int(per_period)
    if required > eligible:
        return eligible
    return required
