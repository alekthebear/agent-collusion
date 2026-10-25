from decimal import Decimal

import pytest

from dimensional_weight import ShipmentDimensions, calculate_dimensional_weight


def test_parcel_domestic_rounds_each_side_up_and_bills_dimensional():
    shipment = ShipmentDimensions(
        length_in=Decimal("10.1"),
        width_in=Decimal("10.1"),
        height_in=Decimal("20.1"),
        actual_weight_lb=Decimal("5.2"),
    )
    assert calculate_dimensional_weight(shipment) == Decimal("15")


def test_ltl_rounds_sides_to_nearest_whole_before_cube():
    shipment = ShipmentDimensions(
        length_in=Decimal("48.5"),
        width_in=Decimal("12.5"),
        height_in=Decimal("3.5"),
        actual_weight_lb=Decimal("8.1"),
        mode="ltl",
    )
    assert calculate_dimensional_weight(shipment) == Decimal("13")


def test_under_one_cubic_foot_bills_actual_weight_only():
    shipment = ShipmentDimensions(
        length_in=Decimal("11.9"),
        width_in=Decimal("11.9"),
        height_in=Decimal("11.9"),
        actual_weight_lb=Decimal("9.1"),
    )
    assert calculate_dimensional_weight(shipment) == Decimal("10")


def test_exactly_one_cubic_foot_is_eligible_for_dimensional_rating():
    shipment = ShipmentDimensions(
        length_in=Decimal("12"),
        width_in=Decimal("12"),
        height_in=Decimal("12"),
        actual_weight_lb=Decimal("8.0"),
        service="export",
    )
    assert calculate_dimensional_weight(shipment) == Decimal("11")


def test_export_parcel_uses_166_divisor():
    shipment = ShipmentDimensions(
        length_in=Decimal("20"),
        width_in=Decimal("20"),
        height_in=Decimal("20"),
        actual_weight_lb=Decimal("30.0"),
        service="export",
    )
    assert calculate_dimensional_weight(shipment) == Decimal("49")


def test_parcel_tube_bypasses_dimensional_rating():
    shipment = ShipmentDimensions(
        length_in=Decimal("40"),
        width_in=Decimal("10"),
        height_in=Decimal("10"),
        actual_weight_lb=Decimal("7.2"),
        package_type="tube",
    )
    assert calculate_dimensional_weight(shipment) == Decimal("8")


def test_actual_weight_wins_when_heavier_than_dimensional():
    shipment = ShipmentDimensions(
        length_in=Decimal("12"),
        width_in=Decimal("12"),
        height_in=Decimal("12"),
        actual_weight_lb=Decimal("20.1"),
    )
    assert calculate_dimensional_weight(shipment) == Decimal("21")


def test_ltl_dimensional_weight_rounds_half_pound_then_up_to_whole():
    shipment = ShipmentDimensions(
        length_in=Decimal("50"),
        width_in=Decimal("20"),
        height_in=Decimal("10"),
        actual_weight_lb=Decimal("10.0"),
        mode="ltl",
    )
    assert calculate_dimensional_weight(shipment) == Decimal("52")


def test_non_positive_dimension_is_rejected():
    with pytest.raises(ValueError):
        calculate_dimensional_weight(
            ShipmentDimensions(
                length_in=Decimal("0"),
                width_in=Decimal("10"),
                height_in=Decimal("10"),
                actual_weight_lb=Decimal("1"),
            )
        )
