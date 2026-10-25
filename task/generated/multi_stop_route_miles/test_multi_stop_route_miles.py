from decimal import Decimal

import pytest

from multi_stop_route_miles import RoutePlan, RouteStop, calculate_multi_stop_route_miles


def test_provided_leg_miles_sum_with_half_up_rounding():
    plan = RoutePlan(
        stops=(
            RouteStop(sequence=1),
            RouteStop(sequence=2, leg_miles_from_previous=Decimal("100.4")),
            RouteStop(sequence=3, leg_miles_from_previous=Decimal("50.5")),
        )
    )
    assert calculate_multi_stop_route_miles(plan) == Decimal("151")


def test_derived_miles_used_when_leg_missing():
    plan = RoutePlan(
        stops=(
            RouteStop(sequence=1, latitude=Decimal("41.8781"), longitude=Decimal("-87.6298")),
            RouteStop(sequence=2, latitude=Decimal("42.3314"), longitude=Decimal("-83.0458")),
        )
    )
    assert calculate_multi_stop_route_miles(plan) == Decimal("280")


def test_very_short_derived_leg_floors_to_one_mile():
    plan = RoutePlan(
        stops=(
            RouteStop(sequence=1, latitude=Decimal("41.0000"), longitude=Decimal("-87.0000")),
            RouteStop(sequence=2, latitude=Decimal("41.0000"), longitude=Decimal("-86.9999")),
        )
    )
    assert calculate_multi_stop_route_miles(plan) == Decimal("1")


def test_out_of_route_within_free_allowance_adds_nothing():
    plan = RoutePlan(
        stops=(
            RouteStop(sequence=1),
            RouteStop(sequence=2, leg_miles_from_previous=Decimal("120")),
        ),
        out_of_route_miles=Decimal("15"),
    )
    assert calculate_multi_stop_route_miles(plan) == Decimal("120")


def test_out_of_route_above_free_allowance_rounds_up():
    plan = RoutePlan(
        stops=(
            RouteStop(sequence=1),
            RouteStop(sequence=2, leg_miles_from_previous=Decimal("120")),
        ),
        out_of_route_miles=Decimal("15.1"),
    )
    assert calculate_multi_stop_route_miles(plan) == Decimal("121")


def test_dense_route_adds_handling_miles_after_fourth_stop():
    plan = RoutePlan(
        stops=(
            RouteStop(sequence=1),
            RouteStop(sequence=2, leg_miles_from_previous=Decimal("10")),
            RouteStop(sequence=3, leg_miles_from_previous=Decimal("10")),
            RouteStop(sequence=4, leg_miles_from_previous=Decimal("10")),
            RouteStop(sequence=5, leg_miles_from_previous=Decimal("10")),
            RouteStop(sequence=6, leg_miles_from_previous=Decimal("10")),
        )
    )
    assert calculate_multi_stop_route_miles(plan) == Decimal("54")


def test_missing_leg_and_coordinates_is_rejected():
    plan = RoutePlan(
        stops=(
            RouteStop(sequence=1),
            RouteStop(sequence=2),
        )
    )
    with pytest.raises(ValueError):
        calculate_multi_stop_route_miles(plan)


def test_first_stop_cannot_have_inbound_leg_miles():
    plan = RoutePlan(
        stops=(
            RouteStop(sequence=1, leg_miles_from_previous=Decimal("5")),
            RouteStop(sequence=2, leg_miles_from_previous=Decimal("10")),
        )
    )
    with pytest.raises(ValueError):
        calculate_multi_stop_route_miles(plan)


def test_stops_must_be_consecutive():
    plan = RoutePlan(
        stops=(
            RouteStop(sequence=1),
            RouteStop(sequence=3, leg_miles_from_previous=Decimal("10")),
        )
    )
    with pytest.raises(ValueError):
        calculate_multi_stop_route_miles(plan)
