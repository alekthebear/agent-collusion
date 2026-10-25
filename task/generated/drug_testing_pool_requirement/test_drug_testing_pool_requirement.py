from decimal import Decimal

import pytest

from drug_testing_pool_requirement import (
    DriverPool,
    TestingPeriod,
    calculate_drug_testing_pool_requirement,
)


def test_monthly_first_period_spreads_annual_target_across_year():
    pool = DriverPool(active_cdl_drivers=100)
    period = TestingPeriod(annual_rate=Decimal("0.50"), cadence="monthly", period_number=1)
    assert calculate_drug_testing_pool_requirement(pool, period) == 5


def test_quarterly_rounds_annual_target_half_up():
    pool = DriverPool(active_cdl_drivers=5)
    period = TestingPeriod(annual_rate=Decimal("0.50"), cadence="quarterly", period_number=1)
    assert calculate_drug_testing_pool_requirement(pool, period) == 1


def test_remaining_requirement_rounds_up_for_current_period():
    pool = DriverPool(active_cdl_drivers=40)
    period = TestingPeriod(
        annual_rate=Decimal("0.25"), cadence="quarterly", period_number=3, prior_random_selections=4
    )
    assert calculate_drug_testing_pool_requirement(pool, period) == 3


def test_noncovered_and_long_term_leave_are_excluded_but_leased_drivers_count():
    pool = DriverPool(
        active_cdl_drivers=50,
        noncovered_drivers=5,
        long_term_leave_drivers=10,
        leased_owner_operators=3,
    )
    period = TestingPeriod(annual_rate=Decimal("0.50"), cadence="monthly", period_number=1)
    assert calculate_drug_testing_pool_requirement(pool, period) == 2


def test_zero_rate_requires_no_selections():
    pool = DriverPool(active_cdl_drivers=80)
    period = TestingPeriod(annual_rate=Decimal("0.00"), cadence="monthly", period_number=6)
    assert calculate_drug_testing_pool_requirement(pool, period) == 0


def test_prior_selections_at_or_above_target_return_zero():
    pool = DriverPool(active_cdl_drivers=20)
    period = TestingPeriod(
        annual_rate=Decimal("0.50"), cadence="quarterly", period_number=4, prior_random_selections=10
    )
    assert calculate_drug_testing_pool_requirement(pool, period) == 0


def test_requirement_is_capped_at_eligible_population():
    pool = DriverPool(active_cdl_drivers=5)
    period = TestingPeriod(
        annual_rate=Decimal("2.00"), cadence="monthly", period_number=12, prior_random_selections=0
    )
    assert calculate_drug_testing_pool_requirement(pool, period) == 5


def test_negative_counts_are_rejected():
    pool = DriverPool(active_cdl_drivers=10, long_term_leave_drivers=-1)
    period = TestingPeriod(annual_rate=Decimal("0.50"), cadence="monthly", period_number=1)
    with pytest.raises(ValueError):
        calculate_drug_testing_pool_requirement(pool, period)


def test_invalid_period_number_for_cadence_is_rejected():
    pool = DriverPool(active_cdl_drivers=10)
    period = TestingPeriod(annual_rate=Decimal("0.50"), cadence="quarterly", period_number=5)
    with pytest.raises(ValueError):
        calculate_drug_testing_pool_requirement(pool, period)
