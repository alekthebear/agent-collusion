from decimal import Decimal

import pytest

from bounce_distance import BounceRules, BounceTrip, calculate_bounce_distance


def test_standard_loaded_miles_pass_through_when_no_adjustments():
    trip = BounceTrip(loaded_miles_to_next_origin=Decimal("50.0"))
    assert calculate_bounce_distance(trip) == Decimal("50.0")


def test_short_local_move_under_floor_is_zero():
    trip = BounceTrip(loaded_miles_to_next_origin=Decimal("7.9"))
    assert calculate_bounce_distance(trip) == Decimal("0.0")


def test_exact_floor_is_billable_bounce():
    trip = BounceTrip(loaded_miles_to_next_origin=Decimal("8.0"))
    assert calculate_bounce_distance(trip) == Decimal("8.0")


def test_terminal_allowance_applies_even_when_loaded_miles_are_under_floor():
    trip = BounceTrip(loaded_miles_to_next_origin=Decimal("5.0"), to_terminal=True)
    assert calculate_bounce_distance(trip) == Decimal("12.0")


def test_urban_market_factor_rounds_to_nearest_tenth():
    trip = BounceTrip(loaded_miles_to_next_origin=Decimal("10.0"), market_density="urban")
    assert calculate_bounce_distance(trip) == Decimal("11.5")


def test_remote_reefer_with_prebook_credit_combines_adjustments():
    trip = BounceTrip(
        loaded_miles_to_next_origin=Decimal("40.0"),
        market_density="remote",
        equipment_type="reefer",
        prebook_hours=6,
    )
    assert calculate_bounce_distance(trip) == Decimal("54.5")


def test_company_tractor_credit_can_reduce_bounce_to_zero():
    trip = BounceTrip(
        loaded_miles_to_next_origin=Decimal("8.0"),
        company_tractor=True,
        prebook_hours=4,
    )
    assert calculate_bounce_distance(trip) == Decimal("0.0")


def test_hazmat_terminal_move_is_capped():
    trip = BounceTrip(
        loaded_miles_to_next_origin=Decimal("240.0"),
        to_terminal=True,
        equipment_type="hazmat",
    )
    assert calculate_bounce_distance(trip) == Decimal("250.0")


def test_negative_loaded_miles_are_rejected():
    with pytest.raises(ValueError):
        calculate_bounce_distance(BounceTrip(loaded_miles_to_next_origin=Decimal("-1.0")))


def test_invalid_market_density_is_rejected():
    with pytest.raises(ValueError):
        calculate_bounce_distance(
            BounceTrip(loaded_miles_to_next_origin=Decimal("25.0"), market_density="suburban")
        )
