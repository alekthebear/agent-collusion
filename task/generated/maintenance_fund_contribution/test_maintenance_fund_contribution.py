from decimal import Decimal

import pytest

from maintenance_fund_contribution import (
    MaintenanceFundTerms,
    SettlementFacts,
    calculate_maintenance_fund_contribution,
)


def test_mileage_plan_skips_small_settlement_below_threshold():
    facts = SettlementFacts(loaded_miles=49)
    terms = MaintenanceFundTerms(per_loaded_mile=Decimal("0.15"))
    assert calculate_maintenance_fund_contribution(facts, terms) == Decimal("0.00")


def test_mileage_plan_charges_at_threshold_without_surcharge():
    facts = SettlementFacts(loaded_miles=50)
    terms = MaintenanceFundTerms(per_loaded_mile=Decimal("0.15"))
    assert calculate_maintenance_fund_contribution(facts, terms) == Decimal("7.50")


def test_mileage_plan_adds_remote_area_surcharge_above_1200_miles():
    facts = SettlementFacts(loaded_miles=1201)
    terms = MaintenanceFundTerms(per_loaded_mile=Decimal("0.10"))
    assert calculate_maintenance_fund_contribution(facts, terms) == Decimal("127.60")


def test_revenue_plan_skips_when_linehaul_below_minimum():
    facts = SettlementFacts(linehaul_revenue=Decimal("299.99"))
    terms = MaintenanceFundTerms(revenue_percent=Decimal("3.0"))
    assert calculate_maintenance_fund_contribution(facts, terms) == Decimal("0.00")


def test_revenue_plan_rounds_half_up_to_cent():
    facts = SettlementFacts(linehaul_revenue=Decimal("333.50"))
    terms = MaintenanceFundTerms(revenue_percent=Decimal("2.5"))
    assert calculate_maintenance_fund_contribution(facts, terms) == Decimal("8.34")


def test_flat_plan_is_waived_for_long_home_time():
    facts = SettlementFacts(home_time_days=14)
    terms = MaintenanceFundTerms(flat_amount=Decimal("50.00"))
    assert calculate_maintenance_fund_contribution(facts, terms) == Decimal("0.00")


def test_quarter_waiver_zeroes_contribution_regardless_of_basis():
    facts = SettlementFacts(loaded_miles=800, waived_for_quarter=True)
    terms = MaintenanceFundTerms(per_loaded_mile=Decimal("0.12"))
    assert calculate_maintenance_fund_contribution(facts, terms) == Decimal("0.00")


def test_contribution_is_limited_to_remaining_room_under_cap():
    facts = SettlementFacts(loaded_miles=1000, account_balance=Decimal("1990.00"), account_cap=Decimal("2000.00"))
    terms = MaintenanceFundTerms(per_loaded_mile=Decimal("0.15"))
    assert calculate_maintenance_fund_contribution(facts, terms) == Decimal("10.00")


def test_negative_loaded_miles_are_rejected():
    facts = SettlementFacts(loaded_miles=-1)
    terms = MaintenanceFundTerms(per_loaded_mile=Decimal("0.10"))
    with pytest.raises(ValueError):
        calculate_maintenance_fund_contribution(facts, terms)


def test_multiple_funding_bases_are_rejected():
    facts = SettlementFacts(loaded_miles=100)
    terms = MaintenanceFundTerms(
        per_loaded_mile=Decimal("0.10"),
        flat_amount=Decimal("25.00"),
    )
    with pytest.raises(ValueError):
        calculate_maintenance_fund_contribution(facts, terms)
