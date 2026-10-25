from decimal import Decimal

import pytest

from linehaul_rate_per_piece import (
    LinehaulTerms,
    ShipmentPieces,
    calculate_linehaul_rate_per_piece,
)


def test_standard_base_rate_without_minimum_interference():
    shipment = ShipmentPieces(pieces=12, total_weight_lb=1200)
    assert calculate_linehaul_rate_per_piece(shipment) == Decimal("9.85")


def test_ten_piece_threshold_is_inclusive():
    shipment = ShipmentPieces(pieces=10, total_weight_lb=1000)
    assert calculate_linehaul_rate_per_piece(shipment) == Decimal("9.85")


def test_twenty_five_piece_threshold_selects_lower_standard_rate():
    shipment = ShipmentPieces(pieces=25, total_weight_lb=2500)
    assert calculate_linehaul_rate_per_piece(shipment) == Decimal("9.10")


def test_expedited_uses_its_own_tariff_breaks():
    shipment = ShipmentPieces(pieces=25, total_weight_lb=2500, service_level="expedited")
    assert calculate_linehaul_rate_per_piece(shipment) == Decimal("11.90")


def test_average_weight_exactly_150_has_no_oversize_premium():
    shipment = ShipmentPieces(pieces=10, total_weight_lb=1500)
    assert calculate_linehaul_rate_per_piece(shipment) == Decimal("9.85")


def test_average_weight_above_150_adds_oversize_premium():
    shipment = ShipmentPieces(pieces=10, total_weight_lb=1510)
    assert calculate_linehaul_rate_per_piece(shipment) == Decimal("11.03")


def test_liftgate_charge_is_capped_before_dividing_per_piece():
    shipment = ShipmentPieces(pieces=30, total_weight_lb=3000, has_liftgate=True)
    assert calculate_linehaul_rate_per_piece(shipment) == Decimal("10.60")


def test_residential_surcharge_can_raise_total_above_minimum():
    shipment = ShipmentPieces(pieces=8, total_weight_lb=800, residential_delivery=True)
    assert calculate_linehaul_rate_per_piece(shipment) == Decimal("12.75")


def test_single_piece_uses_higher_minimum():
    shipment = ShipmentPieces(pieces=1, total_weight_lb=100)
    assert calculate_linehaul_rate_per_piece(shipment) == Decimal("110.00")


def test_invalid_piece_count_is_rejected():
    with pytest.raises(ValueError):
        calculate_linehaul_rate_per_piece(ShipmentPieces(pieces=0, total_weight_lb=100))
