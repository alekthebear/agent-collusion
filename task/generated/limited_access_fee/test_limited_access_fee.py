from decimal import Decimal

import pytest

from limited_access_fee import (
    LimitedAccessTariff,
    StopFacts,
    calculate_limited_access_fee,
)


def test_delivery_at_limited_access_category_gets_full_base_fee():
    stop = StopFacts(category="school", stop_type="delivery")
    assert calculate_limited_access_fee(stop) == Decimal("72.00")


def test_pickup_uses_reduced_multiplier():
    stop = StopFacts(category="school", stop_type="pickup")
    assert calculate_limited_access_fee(stop) == Decimal("57.60")


def test_non_limited_category_is_free():
    stop = StopFacts(category="warehouse", stop_type="delivery")
    assert calculate_limited_access_fee(stop) == Decimal("0.00")


def test_residential_category_does_not_bill_limited_access():
    stop = StopFacts(category="residential", stop_type="delivery")
    assert calculate_limited_access_fee(stop) == Decimal("0.00")


def test_multiple_matches_still_bill_only_once_per_stop():
    stop = StopFacts(category="church", stop_type="delivery", matched_tags=3)
    assert calculate_limited_access_fee(stop) == Decimal("72.00")


def test_already_applied_suppresses_duplicate_charge():
    stop = StopFacts(category="prison", stop_type="delivery", already_applied=True)
    assert calculate_limited_access_fee(stop) == Decimal("0.00")


def test_remote_add_on_applies_only_when_base_fee_applies():
    qualified = StopFacts(category="military_base", stop_type="delivery", remote_area=True)
    assert calculate_limited_access_fee(qualified) == Decimal("90.50")
    not_qualified = StopFacts(category="warehouse", stop_type="delivery", remote_area=True)
    assert calculate_limited_access_fee(not_qualified) == Decimal("0.00")


def test_fee_is_capped_after_add_on():
    tariff = LimitedAccessTariff(base_fee=Decimal("170.00"), remote_add_on=Decimal("25.00"), fee_cap=Decimal("185.00"))
    stop = StopFacts(category="airport", stop_type="delivery", remote_area=True)
    assert calculate_limited_access_fee(stop, tariff) == Decimal("185.00")


def test_half_up_rounding_applies_to_fractional_tariff_result():
    tariff = LimitedAccessTariff(base_fee=Decimal("72.025"))
    stop = StopFacts(category="port", stop_type="delivery")
    assert calculate_limited_access_fee(stop, tariff) == Decimal("72.03")


def test_invalid_stop_type_is_rejected():
    with pytest.raises(ValueError):
        calculate_limited_access_fee(StopFacts(category="school", stop_type="transfer"))
