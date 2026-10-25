from decimal import Decimal

import pytest

from cross_border_brokerage_fee import (
    BrokerageRequest,
    BrokerageTerms,
    calculate_cross_border_brokerage_fee,
)


def test_informal_single_standard_entry_uses_included_base_fee_only():
    request = BrokerageRequest(
        crossing_type="informal",
        entry_count=1,
        commodity_complexity="standard",
        tariff_treatment="standard",
        declared_value=Decimal("1200.00"),
    )
    assert calculate_cross_border_brokerage_fee(request) == Decimal("42.00")


def test_additional_entries_are_surcharged_after_the_first():
    request = BrokerageRequest(
        crossing_type="formal",
        entry_count=3,
        commodity_complexity="standard",
        tariff_treatment="standard",
        declared_value=Decimal("5000.00"),
    )
    assert calculate_cross_border_brokerage_fee(request) == Decimal("155.00")


def test_complex_commodity_adds_flat_review_fee():
    request = BrokerageRequest(
        crossing_type="informal",
        entry_count=1,
        commodity_complexity="complex",
        tariff_treatment="standard",
        declared_value=Decimal("800.00"),
    )
    assert calculate_cross_border_brokerage_fee(request) == Decimal("69.25")


def test_section_301_adds_tariff_review_fee():
    request = BrokerageRequest(
        crossing_type="formal",
        entry_count=1,
        commodity_complexity="standard",
        tariff_treatment="section_301",
        declared_value=Decimal("9000.00"),
    )
    assert calculate_cross_border_brokerage_fee(request) == Decimal("151.40")


def test_informal_bond_is_waived_below_value_threshold():
    request = BrokerageRequest(
        crossing_type="informal",
        entry_count=1,
        commodity_complexity="standard",
        tariff_treatment="standard",
        declared_value=Decimal("2499.99"),
        customs_bond_required=True,
        customs_bond_amount=Decimal("9.75"),
    )
    assert calculate_cross_border_brokerage_fee(request) == Decimal("42.00")


def test_informal_bond_is_billed_at_threshold_value():
    request = BrokerageRequest(
        crossing_type="informal",
        entry_count=1,
        commodity_complexity="standard",
        tariff_treatment="standard",
        declared_value=Decimal("2500.00"),
        customs_bond_required=True,
        customs_bond_amount=Decimal("9.75"),
    )
    assert calculate_cross_border_brokerage_fee(request) == Decimal("51.75")


def test_formal_high_value_surcharge_applies_only_above_threshold():
    request = BrokerageRequest(
        crossing_type="formal",
        entry_count=1,
        commodity_complexity="standard",
        tariff_treatment="standard",
        declared_value=Decimal("250000.01"),
    )
    assert calculate_cross_border_brokerage_fee(request) == Decimal("173.00")


def test_standard_work_is_capped_but_anti_dumping_is_not():
    capped_request = BrokerageRequest(
        crossing_type="formal",
        entry_count=8,
        commodity_complexity="complex",
        tariff_treatment="section_301",
        declared_value=Decimal("300000.00"),
        customs_bond_required=True,
        customs_bond_amount=Decimal("40.00"),
    )
    assert calculate_cross_border_brokerage_fee(capped_request) == Decimal("325.00")

    uncapped_request = BrokerageRequest(
        crossing_type="formal",
        entry_count=8,
        commodity_complexity="complex",
        tariff_treatment="anti_dumping",
        declared_value=Decimal("300000.00"),
        customs_bond_required=True,
        customs_bond_amount=Decimal("40.00"),
    )
    assert calculate_cross_border_brokerage_fee(uncapped_request) == Decimal("514.75")


def test_zero_entries_returns_zero_even_for_other_flags():
    request = BrokerageRequest(
        crossing_type="formal",
        entry_count=0,
        commodity_complexity="complex",
        tariff_treatment="anti_dumping",
        declared_value=Decimal("500000.00"),
    )
    assert calculate_cross_border_brokerage_fee(request) == Decimal("0.00")


def test_negative_entry_count_is_rejected():
    request = BrokerageRequest(
        crossing_type="formal",
        entry_count=-1,
        commodity_complexity="standard",
        tariff_treatment="standard",
        declared_value=Decimal("100.00"),
    )
    with pytest.raises(ValueError):
        calculate_cross_border_brokerage_fee(request)
