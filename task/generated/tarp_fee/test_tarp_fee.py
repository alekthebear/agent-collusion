from decimal import Decimal

import pytest

from tarp_fee import TarpLoad, TarpTerms, calculate_tarp_fee


def test_standard_steel_tarp_uses_base_rate():
    load = TarpLoad(tarp_count=2, tarp_type="steel", commodity="pipe")
    assert calculate_tarp_fee(load) == Decimal("150.00")


def test_lumber_tarps_use_higher_base_rate():
    load = TarpLoad(tarp_count=2, tarp_type="lumber", commodity="lumber")
    assert calculate_tarp_fee(load) == Decimal("190.00")


def test_weather_sensitive_commodity_adds_per_tarp_surcharge():
    load = TarpLoad(tarp_count=2, tarp_type="steel", commodity="drywall")
    assert calculate_tarp_fee(load) == Decimal("175.00")


def test_smoke_tarps_do_not_receive_weather_surcharge():
    load = TarpLoad(tarp_count=2, tarp_type="smoke", commodity="paper")
    assert calculate_tarp_fee(load) == Decimal("70.00")


def test_machinery_adds_one_flat_edge_protection_surcharge():
    load = TarpLoad(tarp_count=1, tarp_type="steel", commodity="machinery")
    assert calculate_tarp_fee(load) == Decimal("95.00")


def test_discount_applies_only_after_second_tarp():
    load = TarpLoad(tarp_count=4, tarp_type="steel", commodity="pipe")
    assert calculate_tarp_fee(load) == Decimal("290.00")


def test_required_tarp_with_missing_count_bills_minimum_one_tarp():
    load = TarpLoad(tarp_count=0, tarp_type="steel", commodity="pipe", tarp_required=True)
    assert calculate_tarp_fee(load) == Decimal("75.00")


def test_not_required_means_no_fee_even_with_count_present():
    load = TarpLoad(tarp_count=3, tarp_type="steel", commodity="pipe", tarp_required=False)
    assert calculate_tarp_fee(load) == Decimal("0.00")


def test_tarp_included_overrides_other_charges():
    load = TarpLoad(tarp_count=3, tarp_type="lumber", commodity="drywall", tarp_included=True)
    assert calculate_tarp_fee(load) == Decimal("0.00")


def test_custom_schedule_can_be_used_for_carrier_compensation():
    terms = TarpTerms(schedule={"steel": Decimal("90.00"), "lumber": Decimal("110.00"), "smoke": Decimal("40.00")})
    load = TarpLoad(tarp_count=3, tarp_type="steel", commodity="pipe")
    assert calculate_tarp_fee(load, terms) == Decimal("265.00")


def test_excessive_tarp_count_is_rejected():
    with pytest.raises(ValueError):
        calculate_tarp_fee(TarpLoad(tarp_count=9, tarp_type="steel", commodity="pipe"))
