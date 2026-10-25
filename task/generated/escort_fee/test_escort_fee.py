from decimal import Decimal

import pytest

from escort_fee import EscortContract, EscortPlan, RouteSegment, calculate_escort_fee


def test_no_escort_required_is_free_even_with_flags():
    plan = EscortPlan(
        segments=(RouteSegment(Decimal("42.7"), 0, "TX", night_move=True, metro_area=True),),
    )
    assert calculate_escort_fee(plan) == Decimal("0.00")


def test_fractional_miles_round_up_before_pricing():
    plan = EscortPlan(
        segments=(RouteSegment(Decimal("12.1"), 1, "TX"),),
    )
    assert calculate_escort_fee(plan) == Decimal("31.20")


def test_minimum_billed_miles_applies_to_short_segment():
    plan = EscortPlan(
        segments=(RouteSegment(Decimal("4.2"), 1, "TX"),),
    )
    assert calculate_escort_fee(plan) == Decimal("24.00")


def test_two_escorts_double_segment_charge_and_night_is_per_escort():
    plan = EscortPlan(
        segments=(RouteSegment(Decimal("10.0"), 2, "TX", night_move=True),),
    )
    assert calculate_escort_fee(plan) == Decimal("118.00")


def test_metro_surcharge_applies_once_per_segment_not_per_escort():
    plan = EscortPlan(
        segments=(RouteSegment(Decimal("10.0"), 2, "TX", metro_area=True),),
    )
    assert calculate_escort_fee(plan) == Decimal("73.00")


def test_special_jurisdiction_adds_admin_fee():
    plan = EscortPlan(
        segments=(RouteSegment(Decimal("10.0"), 1, "CA"),),
    )
    assert calculate_escort_fee(plan) == Decimal("42.50")


def test_markup_billing_rounds_half_up_on_per_trip_subtotal():
    contract = EscortContract(base_rate_per_mile=Decimal("2.40"), billing_mode="markup", markup_percent=Decimal("12.5"))
    plan = EscortPlan(
        segments=(RouteSegment(Decimal("10.0"), 1, "TX"),),
    )
    assert calculate_escort_fee(plan, contract) == Decimal("27.00")


def test_three_or_more_trips_receive_discount_after_billing():
    plan = EscortPlan(
        segments=(RouteSegment(Decimal("10.0"), 1, "TX"),),
        trips=3,
    )
    assert calculate_escort_fee(plan) == Decimal("68.40")


def test_pass_through_cannot_include_markup_percent():
    contract = EscortContract(billing_mode="pass_through", markup_percent=Decimal("5.00"))
    plan = EscortPlan(segments=(RouteSegment(Decimal("10.0"), 1, "TX"),))
    with pytest.raises(ValueError):
        calculate_escort_fee(plan, contract)


def test_invalid_escort_count_is_rejected():
    plan = EscortPlan(segments=(RouteSegment(Decimal("10.0"), 3, "TX"),))
    with pytest.raises(ValueError):
        calculate_escort_fee(plan)
