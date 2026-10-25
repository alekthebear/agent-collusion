from decimal import Decimal

import pytest

from mileage_band_pricing import LaneProfile, PricingTerms, calculate_mileage_band_pricing


def test_short_shuttle_uses_contract_minimum_charge():
    profile = LaneProfile(miles=20)
    assert calculate_mileage_band_pricing(profile) == Decimal("185.00")


def test_band_boundary_at_49_miles_still_floors_to_minimum():
    profile = LaneProfile(miles=49)
    assert calculate_mileage_band_pricing(profile) == Decimal("185.00")


def test_band_boundary_at_50_miles_uses_next_band():
    profile = LaneProfile(miles=50)
    assert calculate_mileage_band_pricing(profile) == Decimal("285.00")


def test_eastbound_premium_applies_at_300_miles():
    profile = LaneProfile(miles=300, direction="E")
    assert calculate_mileage_band_pricing(profile) == Decimal("760.00")


def test_westbound_longhaul_gets_no_directional_premium():
    profile = LaneProfile(miles=300, direction="W")
    assert calculate_mileage_band_pricing(profile) == Decimal("690.00")


def test_remote_region_surcharge_does_not_apply_below_100_miles():
    profile = LaneProfile(miles=99, region="remote")
    assert calculate_mileage_band_pricing(profile) == Decimal("285.00")


def test_mountain_region_adds_half_remote_surcharge():
    profile = LaneProfile(miles=150, region="mountain")
    assert calculate_mileage_band_pricing(profile) == Decimal("512.50")


def test_breakpoint_discount_applies_only_on_qualifying_longhaul_subtotal():
    profile = LaneProfile(miles=700)
    assert calculate_mileage_band_pricing(profile) == Decimal("1100.00")


def test_hazmat_is_applied_after_breakpoint_discount():
    profile = LaneProfile(miles=700, hazmat=True)
    assert calculate_mileage_band_pricing(profile) == Decimal("1232.00")


def test_negative_miles_are_rejected():
    with pytest.raises(ValueError):
        calculate_mileage_band_pricing(LaneProfile(miles=-1))
