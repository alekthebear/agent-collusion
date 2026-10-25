from decimal import Decimal

import pytest

from fuel_stop_planner import FuelPlanInput, calculate_fuel_stop_plan


def test_standard_route_uses_rounded_down_25_mile_leg_range():
    plan = calculate_fuel_stop_plan(
        FuelPlanInput(
            route_miles=Decimal("600"),
            usable_gallons=Decimal("120"),
            reserve_gallons=Decimal("20"),
            mpg=Decimal("6.5"),
        )
    )
    assert plan.effective_range_miles == Decimal("630.50")
    assert plan.planned_leg_range_miles == 625
    assert plan.planned_stop_count == 0
    assert plan.average_leg_miles == 600


def test_mountain_route_reduces_range_and_can_add_a_stop():
    plan = calculate_fuel_stop_plan(
        FuelPlanInput(
            route_miles=Decimal("600"),
            usable_gallons=Decimal("120"),
            reserve_gallons=Decimal("20"),
            mpg=Decimal("6.5"),
            mountain_route=True,
        )
    )
    assert plan.effective_range_miles == Decimal("598.00")
    assert plan.planned_leg_range_miles == 575
    assert plan.planned_stop_count == 1
    assert plan.average_leg_miles == 300


def test_reefer_support_applies_extra_discount():
    plan = calculate_fuel_stop_plan(
        FuelPlanInput(
            route_miles=Decimal("600"),
            usable_gallons=Decimal("120"),
            reserve_gallons=Decimal("20"),
            mpg=Decimal("6.5"),
            reefer_support=True,
        )
    )
    assert plan.effective_range_miles == Decimal("598.98")
    assert plan.planned_leg_range_miles == 575


def test_short_haul_exemption_returns_zero_stops():
    plan = calculate_fuel_stop_plan(
        FuelPlanInput(
            route_miles=Decimal("150"),
            usable_gallons=Decimal("30"),
            reserve_gallons=Decimal("5"),
            mpg=Decimal("4"),
        )
    )
    assert plan.planned_stop_count == 0
    assert plan.average_leg_miles == 150
    assert plan.planned_leg_range_miles == 100


def test_nuisance_stop_is_removed_when_average_leg_is_just_under_threshold():
    plan = calculate_fuel_stop_plan(
        FuelPlanInput(
            route_miles=Decimal("350"),
            usable_gallons=Decimal("30"),
            reserve_gallons=Decimal("5"),
            mpg=Decimal("6"),
        )
    )
    assert plan.effective_range_miles == Decimal("145.50")
    assert plan.planned_leg_range_miles == 125
    assert plan.planned_stop_count == 2
    assert plan.average_leg_miles == 117


def test_nuisance_stop_is_not_removed_when_reduced_plan_exceeds_tolerance():
    plan = calculate_fuel_stop_plan(
        FuelPlanInput(
            route_miles=Decimal("390"),
            usable_gallons=Decimal("30"),
            reserve_gallons=Decimal("5"),
            mpg=Decimal("6"),
        )
    )
    assert plan.planned_stop_count == 2
    assert plan.average_leg_miles == 130
    assert plan.planned_leg_range_miles == 125


def test_minimum_leg_range_is_100_miles_for_positive_effective_range():
    plan = calculate_fuel_stop_plan(
        FuelPlanInput(
            route_miles=Decimal("220"),
            usable_gallons=Decimal("12"),
            reserve_gallons=Decimal("2"),
            mpg=Decimal("5"),
        )
    )
    assert plan.effective_range_miles == Decimal("48.50")
    assert plan.planned_leg_range_miles == 100
    assert plan.planned_stop_count == 1
    assert plan.average_leg_miles == 110


def test_zero_route_miles_returns_zero_leg_average():
    plan = calculate_fuel_stop_plan(
        FuelPlanInput(
            route_miles=Decimal("0"),
            usable_gallons=Decimal("50"),
            reserve_gallons=Decimal("10"),
            mpg=Decimal("7"),
        )
    )
    assert plan.planned_stop_count == 0
    assert plan.average_leg_miles == 0
    assert plan.planned_leg_range_miles == 250


def test_reserve_must_be_less_than_usable():
    with pytest.raises(ValueError):
        calculate_fuel_stop_plan(
            FuelPlanInput(
                route_miles=Decimal("100"),
                usable_gallons=Decimal("40"),
                reserve_gallons=Decimal("40"),
                mpg=Decimal("6"),
            )
        )
