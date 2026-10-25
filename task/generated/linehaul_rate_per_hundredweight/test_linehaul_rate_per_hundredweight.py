from decimal import Decimal

import pytest

from linehaul_rate_per_hundredweight import LinehaulShipment, calculate_linehaul_rate_per_hundredweight


def test_under_500_uses_first_weight_break():
    shipment = LinehaulShipment(billed_weight_lb=400, freight_class=70, origin_state="TX", destination_state="OK")
    assert calculate_linehaul_rate_per_hundredweight(shipment) == Decimal("38.60")


def test_exact_500_enters_second_weight_break():
    shipment = LinehaulShipment(billed_weight_lb=500, freight_class=70, origin_state="TX", destination_state="OK")
    assert calculate_linehaul_rate_per_hundredweight(shipment) == Decimal("33.70")


def test_discount_reduces_rate_before_other_rules():
    shipment = LinehaulShipment(
        billed_weight_lb=1000,
        freight_class=92,
        origin_state="IL",
        destination_state="MO",
        discount_percent=Decimal("25"),
    )
    assert calculate_linehaul_rate_per_hundredweight(shipment) == Decimal("25.58")


def test_remote_area_uplift_applies_on_hawaii_lanes():
    shipment = LinehaulShipment(billed_weight_lb=500, freight_class=50, origin_state="CA", destination_state="HI")
    assert calculate_linehaul_rate_per_hundredweight(shipment) == Decimal("31.47")


def test_fragile_uplift_applies_below_2000_pounds_only():
    shipment = LinehaulShipment(billed_weight_lb=1500, freight_class=125, origin_state="GA", destination_state="FL")
    assert calculate_linehaul_rate_per_hundredweight(shipment) == Decimal("44.60")


def test_fragile_uplift_drops_off_at_2000_pounds():
    shipment = LinehaulShipment(billed_weight_lb=2000, freight_class=125, origin_state="GA", destination_state="FL")
    assert calculate_linehaul_rate_per_hundredweight(shipment) == Decimal("37.60")


def test_deficit_rating_applies_within_150_pounds_when_cheaper():
    shipment = LinehaulShipment(billed_weight_lb=4900, freight_class=125, origin_state="OH", destination_state="PA")
    assert calculate_linehaul_rate_per_hundredweight(shipment) == Decimal("33.88")


def test_deficit_rating_does_not_apply_outside_window():
    shipment = LinehaulShipment(billed_weight_lb=4849, freight_class=125, origin_state="OH", destination_state="PA")
    assert calculate_linehaul_rate_per_hundredweight(shipment) == Decimal("37.60")


def test_minimum_charge_controls_small_discounted_shipment():
    shipment = LinehaulShipment(
        billed_weight_lb=100,
        freight_class=50,
        origin_state="TX",
        destination_state="NM",
        discount_percent=Decimal("80"),
    )
    assert calculate_linehaul_rate_per_hundredweight(shipment) == Decimal("85.00")


def test_invalid_freight_class_is_rejected():
    with pytest.raises(ValueError):
        calculate_linehaul_rate_per_hundredweight(
            LinehaulShipment(billed_weight_lb=500, freight_class=77, origin_state="TX", destination_state="OK")
        )
