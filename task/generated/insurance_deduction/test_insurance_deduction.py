from datetime import date
from decimal import Decimal

import pytest

from insurance_deduction import (
    ContributionSchedule,
    CoverageElection,
    InsuranceContext,
    calculate_insurance_deduction,
)


def d(day):
    return date(2026, 4, day)


def test_full_week_all_coverages_bills_weekly_total():
    elections = CoverageElection(True, True, True)
    ctx = InsuranceContext(settlement_start=d(1), settlement_end=d(7), enrollment_start=d(1))
    assert calculate_insurance_deduction(elections, ctx) == Decimal("57.81")


def test_occupational_accident_waiting_day_skips_effective_date():
    elections = CoverageElection(occupational_accident=True)
    ctx = InsuranceContext(settlement_start=d(1), settlement_end=d(1), enrollment_start=d(1))
    assert calculate_insurance_deduction(elections, ctx) == Decimal("0.00")


def test_partial_week_prorates_and_rounds_half_up():
    elections = CoverageElection(physical_damage=True)
    ctx = InsuranceContext(settlement_start=d(1), settlement_end=d(3), enrollment_start=d(1))
    assert calculate_insurance_deduction(elections, ctx) == Decimal("8.04")


def test_company_owned_truck_blocks_physical_damage_deduction():
    elections = CoverageElection(physical_damage=True)
    ctx = InsuranceContext(
        settlement_start=d(1), settlement_end=d(7), enrollment_start=d(1), truck_company_owned=True
    )
    assert calculate_insurance_deduction(elections, ctx) == Decimal("0.00")


def test_hazmat_only_low_value_waives_cargo_buyup():
    elections = CoverageElection(cargo_buyup=True)
    ctx = InsuranceContext(
        settlement_start=d(1),
        settlement_end=d(7),
        enrollment_start=d(1),
        hazmat_only=True,
        insured_value=Decimal("100000.00"),
    )
    assert calculate_insurance_deduction(elections, ctx) == Decimal("0.00")


def test_hazmat_only_above_threshold_bills_cargo_buyup():
    elections = CoverageElection(cargo_buyup=True)
    ctx = InsuranceContext(
        settlement_start=d(1),
        settlement_end=d(7),
        enrollment_start=d(1),
        hazmat_only=True,
        insured_value=Decimal("100000.01"),
    )
    assert calculate_insurance_deduction(elections, ctx) == Decimal("11.20")


def test_termination_stops_billing_after_termination_date():
    elections = CoverageElection(physical_damage=True)
    ctx = InsuranceContext(
        settlement_start=d(1), settlement_end=d(7), enrollment_start=d(1), termination_date=d(4)
    )
    assert calculate_insurance_deduction(elections, ctx) == Decimal("10.71")


def test_small_subtotal_is_waived():
    elections = CoverageElection(cargo_buyup=True)
    ctx = InsuranceContext(settlement_start=d(1), settlement_end=d(2), enrollment_start=d(1))
    assert calculate_insurance_deduction(elections, ctx) == Decimal("0.00")


def test_total_is_capped_per_settlement():
    elections = CoverageElection(True, True, True)
    schedule = ContributionSchedule(
        occupational_accident_weekly=Decimal("140.00"),
        physical_damage_weekly=Decimal("70.00"),
        cargo_buyup_weekly=Decimal("35.00"),
    )
    ctx = InsuranceContext(settlement_start=d(1), settlement_end=d(7), enrollment_start=d(1))
    assert calculate_insurance_deduction(elections, ctx, schedule) == Decimal("125.00")


def test_invalid_settlement_dates_are_rejected():
    elections = CoverageElection()
    ctx = InsuranceContext(settlement_start=d(7), settlement_end=d(1), enrollment_start=d(1))
    with pytest.raises(ValueError):
        calculate_insurance_deduction(elections, ctx)
