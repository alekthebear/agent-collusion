from decimal import Decimal

import pytest

from yard_move_time import YardMoveRequest, calculate_yard_move_time


def test_small_facility_uses_small_base_and_ready_credit():
    request = YardMoveRequest(facility_acres=80, spot_distance_miles=Decimal("0.2"))
    assert calculate_yard_move_time(request) == Decimal("8.40")


def test_medium_facility_starts_above_small_threshold():
    request = YardMoveRequest(facility_acres=81, spot_distance_miles=Decimal("0.2"))
    assert calculate_yard_move_time(request) == Decimal("11.40")


def test_large_facility_starts_above_medium_threshold():
    request = YardMoveRequest(facility_acres=201, spot_distance_miles=Decimal("0.2"))
    assert calculate_yard_move_time(request) == Decimal("15.40")


def test_partial_tenth_mile_rounds_up():
    request = YardMoveRequest(facility_acres=50, spot_distance_miles=Decimal("0.21"))
    assert calculate_yard_move_time(request) == Decimal("9.60")


def test_congestion_applies_only_to_variable_portion():
    request = YardMoveRequest(
        facility_acres=100,
        spot_distance_miles=Decimal("0.5"),
        congestion_factor=Decimal("1.25"),
    )
    assert calculate_yard_move_time(request) == Decimal("16.25")


def test_not_ready_loaded_gets_larger_penalty_than_empty():
    loaded = YardMoveRequest(
        facility_acres=100,
        spot_distance_miles=Decimal("0.3"),
        trailer_ready=False,
        loaded=True,
    )
    empty = YardMoveRequest(
        facility_acres=100,
        spot_distance_miles=Decimal("0.3"),
        trailer_ready=False,
        loaded=False,
    )
    assert calculate_yard_move_time(loaded) == Decimal("17.60")
    assert calculate_yard_move_time(empty) == Decimal("15.60")


def test_same_row_credit_reduces_final_total():
    request = YardMoveRequest(
        facility_acres=50,
        spot_distance_miles=Decimal("0.4"),
        same_row=True,
    )
    assert calculate_yard_move_time(request) == Decimal("9.30")


def test_minimum_minutes_floor_applies_after_credits():
    request = YardMoveRequest(
        facility_acres=10,
        spot_distance_miles=Decimal("0.0"),
        same_row=True,
    )
    assert calculate_yard_move_time(request) == Decimal("6.00")


def test_invalid_congestion_factor_is_rejected():
    with pytest.raises(ValueError):
        calculate_yard_move_time(
            YardMoveRequest(facility_acres=50, spot_distance_miles=Decimal("0.2"), congestion_factor=Decimal("1.61"))
        )


def test_negative_distance_is_rejected():
    with pytest.raises(ValueError):
        calculate_yard_move_time(
            YardMoveRequest(facility_acres=50, spot_distance_miles=Decimal("-0.1"))
        )
