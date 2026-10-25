from decimal import Decimal

import pytest

from trailer_cost_per_day import (
    FinancingTerms,
    FixedExpenses,
    TrailerProfile,
    calculate_trailer_cost_per_day,
)


def test_owned_trailer_combines_depreciation_financing_and_fixed_expenses():
    profile = TrailerProfile(
        purchase_price=Decimal("35000.00"),
        salvage_value=Decimal("5000.00"),
        service_years=5,
        useful_life_years=10,
    )
    financing = FinancingTerms(
        opening_principal=Decimal("12000.00"),
        annual_interest_rate=Decimal("0.12"),
        scheduled_principal_paid=Decimal("2400.00"),
    )
    fixed = FixedExpenses(
        registration=Decimal("800.00"),
        insurance=Decimal("1200.00"),
        permits=Decimal("300.00"),
        telematics=Decimal("620.00"),
        available_days=365,
    )
    assert calculate_trailer_cost_per_day(profile, financing, fixed) == Decimal("19.77")


def test_leased_trailer_uses_lease_cost_instead_of_depreciation_and_financing():
    profile = TrailerProfile(
        purchase_price=Decimal("40000.00"),
        salvage_value=Decimal("5000.00"),
        service_years=3,
        useful_life_years=12,
        leased=True,
    )
    financing = FinancingTerms(
        opening_principal=Decimal("15000.00"),
        annual_interest_rate=Decimal("0.10"),
        scheduled_principal_paid=Decimal("3000.00"),
        annual_lease_cost=Decimal("9000.00"),
    )
    fixed = FixedExpenses(insurance=Decimal("1825.00"), available_days=365)
    assert calculate_trailer_cost_per_day(profile, financing, fixed) == Decimal("29.66")


def test_reefer_adds_daily_surcharge():
    profile = TrailerProfile(
        purchase_price=Decimal("3650.00"),
        salvage_value=Decimal("0.00"),
        service_years=2,
        useful_life_years=1,
        refrigerated=True,
    )
    fixed = FixedExpenses(available_days=365)
    assert calculate_trailer_cost_per_day(profile, FinancingTerms(), fixed) == Decimal("11.75")


def test_age_reserve_starts_after_ten_years_not_at_ten():
    ten_year = TrailerProfile(
        purchase_price=Decimal("3650.00"),
        salvage_value=Decimal("0.00"),
        service_years=10,
        useful_life_years=1,
    )
    eleven_year = TrailerProfile(
        purchase_price=Decimal("3650.00"),
        salvage_value=Decimal("0.00"),
        service_years=11,
        useful_life_years=1,
    )
    fixed = FixedExpenses(available_days=365)
    assert calculate_trailer_cost_per_day(ten_year, fixed=fixed) == Decimal("10.00")
    assert calculate_trailer_cost_per_day(eleven_year, fixed=fixed) == Decimal("12.40")


def test_very_old_reserve_starts_after_fifteen_years():
    profile = TrailerProfile(
        purchase_price=Decimal("3650.00"),
        salvage_value=Decimal("0.00"),
        service_years=16,
        useful_life_years=1,
    )
    fixed = FixedExpenses(available_days=365)
    assert calculate_trailer_cost_per_day(profile, fixed=fixed) == Decimal("14.10")


def test_financing_closing_balance_cannot_go_below_zero():
    profile = TrailerProfile(
        purchase_price=Decimal("0.00"),
        salvage_value=Decimal("0.00"),
        service_years=1,
        useful_life_years=5,
    )
    financing = FinancingTerms(
        opening_principal=Decimal("1000.00"),
        annual_interest_rate=Decimal("0.12"),
        scheduled_principal_paid=Decimal("1500.00"),
    )
    fixed = FixedExpenses(available_days=365)
    assert calculate_trailer_cost_per_day(profile, financing, fixed) == Decimal("0.16")


def test_available_days_boundary_of_366_is_allowed():
    profile = TrailerProfile(
        purchase_price=Decimal("3660.00"),
        salvage_value=Decimal("0.00"),
        service_years=1,
        useful_life_years=1,
    )
    fixed = FixedExpenses(available_days=366)
    assert calculate_trailer_cost_per_day(profile, fixed=fixed) == Decimal("10.00")


def test_invalid_available_days_is_rejected():
    profile = TrailerProfile(
        purchase_price=Decimal("1000.00"),
        salvage_value=Decimal("0.00"),
        service_years=1,
        useful_life_years=1,
    )
    with pytest.raises(ValueError):
        calculate_trailer_cost_per_day(profile, fixed=FixedExpenses(available_days=0))


def test_salvage_cannot_exceed_purchase_price():
    profile = TrailerProfile(
        purchase_price=Decimal("5000.00"),
        salvage_value=Decimal("5000.01"),
        service_years=1,
        useful_life_years=5,
    )
    with pytest.raises(ValueError):
        calculate_trailer_cost_per_day(profile)
