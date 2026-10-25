from decimal import Decimal

import pytest

from tire_wear_cost import TireSet, TireUsage, calculate_tire_wear_cost


def test_zero_miles_returns_zero_cost():
    tire = TireSet(purchase_cost=Decimal("500.00"), expected_life_miles=100000)
    usage = TireUsage(position="drive", miles_driven=0)
    assert calculate_tire_wear_cost(tire, usage) == Decimal("0.0000")


def test_drive_position_uses_base_life_without_retreads():
    tire = TireSet(purchase_cost=Decimal("500.00"), expected_life_miles=100000)
    usage = TireUsage(position="drive", miles_driven=1000)
    assert calculate_tire_wear_cost(tire, usage) == Decimal("5.0000")


def test_trailer_position_lasts_longer_than_drive():
    tire = TireSet(purchase_cost=Decimal("540.00"), expected_life_miles=100000)
    usage = TireUsage(position="trailer", miles_driven=1000)
    assert calculate_tire_wear_cost(tire, usage) == Decimal("5.0000")


def test_steer_position_ignores_retread_cycles():
    tire = TireSet(
        purchase_cost=Decimal("600.00"),
        expected_life_miles=100000,
        retread_cost=Decimal("120.00"),
        retread_cycles=2,
    )
    usage = TireUsage(position="steer", miles_driven=920)
    assert calculate_tire_wear_cost(tire, usage) == Decimal("6.0000")


def test_retreads_add_cost_and_miles_for_drive_position():
    tire = TireSet(
        purchase_cost=Decimal("400.00"),
        expected_life_miles=100000,
        retread_cost=Decimal("100.00"),
        retread_cycles=2,
    )
    usage = TireUsage(position="drive", miles_driven=2700)
    assert calculate_tire_wear_cost(tire, usage) == Decimal("6.0000")


def test_retread_cycles_are_capped_at_three():
    tire = TireSet(
        purchase_cost=Decimal("400.00"),
        expected_life_miles=100000,
        retread_cost=Decimal("100.00"),
        retread_cycles=5,
    )
    usage = TireUsage(position="drive", miles_driven=3550)
    assert calculate_tire_wear_cost(tire, usage) == Decimal("7.0000")


def test_severe_service_reduces_usable_miles_and_increases_cost():
    tire = TireSet(purchase_cost=Decimal("500.00"), expected_life_miles=100000)
    usage = TireUsage(position="drive", miles_driven=900, severe_service_factor=Decimal("0.90"))
    assert calculate_tire_wear_cost(tire, usage) == Decimal("5.0000")


def test_rounds_half_up_to_four_decimals():
    tire = TireSet(purchase_cost=Decimal("1.00"), expected_life_miles=16000)
    usage = TireUsage(position="drive", miles_driven=8)
    assert calculate_tire_wear_cost(tire, usage) == Decimal("0.0005")


def test_expected_life_below_minimum_is_rejected():
    tire = TireSet(purchase_cost=Decimal("300.00"), expected_life_miles=9999)
    usage = TireUsage(position="drive", miles_driven=100)
    with pytest.raises(ValueError):
        calculate_tire_wear_cost(tire, usage)


def test_unknown_position_is_rejected():
    tire = TireSet(purchase_cost=Decimal("300.00"), expected_life_miles=50000)
    usage = TireUsage(position="bogie", miles_driven=100)
    with pytest.raises(ValueError):
        calculate_tire_wear_cost(tire, usage)
