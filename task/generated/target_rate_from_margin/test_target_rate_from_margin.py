from decimal import Decimal

import pytest

from target_rate_from_margin import MarginTarget, ShipmentProfile, calculate_target_rate_from_margin


def test_margin_formula_applies_when_above_floors():
    shipment = ShipmentProfile(projected_cost=Decimal("500.00"))
    target = MarginTarget(gross_margin_percent=Decimal("0.20"))
    assert calculate_target_rate_from_margin(shipment, target) == Decimal("625.00")


def test_low_cost_load_uses_85_profit_floor_when_margin_result_is_too_low():
    shipment = ShipmentProfile(projected_cost=Decimal("300.00"))
    target = MarginTarget(gross_margin_percent=Decimal("0.10"))
    assert calculate_target_rate_from_margin(shipment, target) == Decimal("385.00")


def test_cost_at_400_uses_125_profit_floor_boundary():
    shipment = ShipmentProfile(projected_cost=Decimal("400.00"))
    target = MarginTarget(gross_margin_percent=Decimal("0.10"))
    assert calculate_target_rate_from_margin(shipment, target) == Decimal("525.00")


def test_pass_through_surcharges_are_added_to_customer_total():
    shipment = ShipmentProfile(
        projected_cost=Decimal("500.00"),
        fuel_surcharge=Decimal("60.00"),
        other_surcharges=Decimal("15.00"),
    )
    target = MarginTarget(gross_margin_percent=Decimal("0.20"))
    assert calculate_target_rate_from_margin(shipment, target) == Decimal("700.00")


def test_reefer_and_hazmat_premiums_stack_on_linehaul():
    shipment = ShipmentProfile(
        projected_cost=Decimal("500.00"),
        is_reefer=True,
        is_hazmat=True,
    )
    target = MarginTarget(gross_margin_percent=Decimal("0.20"))
    assert calculate_target_rate_from_margin(shipment, target) == Decimal("750.00")


def test_partial_discount_applies_when_above_minimum_profit_guardrail():
    shipment = ShipmentProfile(projected_cost=Decimal("500.00"), is_partial=True)
    target = MarginTarget(gross_margin_percent=Decimal("0.20"))
    assert calculate_target_rate_from_margin(shipment, target) == Decimal("581.00")


def test_partial_never_goes_below_cost_plus_40_profit():
    shipment = ShipmentProfile(projected_cost=Decimal("100.00"), is_partial=True)
    target = MarginTarget(gross_margin_percent=Decimal("0.00"))
    assert calculate_target_rate_from_margin(shipment, target) == Decimal("140.00")


def test_all_in_floor_applies_to_tiny_quote():
    shipment = ShipmentProfile(projected_cost=Decimal("50.00"), is_partial=True)
    target = MarginTarget(gross_margin_percent=Decimal("0.00"))
    assert calculate_target_rate_from_margin(shipment, target) == Decimal("125.00")


def test_invalid_margin_at_or_above_50_percent_is_rejected():
    shipment = ShipmentProfile(projected_cost=Decimal("500.00"))
    with pytest.raises(ValueError):
        calculate_target_rate_from_margin(shipment, MarginTarget(gross_margin_percent=Decimal("0.50")))


def test_negative_surcharge_is_rejected():
    shipment = ShipmentProfile(projected_cost=Decimal("500.00"), fuel_surcharge=Decimal("-1.00"))
    with pytest.raises(ValueError):
        calculate_target_rate_from_margin(shipment, MarginTarget(gross_margin_percent=Decimal("0.20")))
