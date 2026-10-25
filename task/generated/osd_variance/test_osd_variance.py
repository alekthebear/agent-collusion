from decimal import Decimal

import pytest

from osd_variance import ShipmentQuantities, VarianceTerms, calculate_osd_variance


def test_exact_match_has_no_variance():
    qty = ShipmentQuantities(
        tendered_units=Decimal("100"),
        loaded_units=Decimal("100"),
        delivered_units=Decimal("100"),
    )
    assert calculate_osd_variance(qty) == Decimal("0.00")


def test_shortage_within_percent_tolerance_is_ignored():
    qty = ShipmentQuantities(
        tendered_units=Decimal("100"),
        loaded_units=Decimal("100"),
        delivered_units=Decimal("99.60"),
    )
    assert calculate_osd_variance(qty) == Decimal("0.00")


def test_shortage_outside_tolerance_returns_negative_units():
    qty = ShipmentQuantities(
        tendered_units=Decimal("100"),
        loaded_units=Decimal("100"),
        delivered_units=Decimal("98.99"),
    )
    assert calculate_osd_variance(qty) == Decimal("-1.01")


def test_damage_reduces_clean_delivery():
    qty = ShipmentQuantities(
        tendered_units=Decimal("100"),
        loaded_units=Decimal("100"),
        delivered_units=Decimal("100"),
        damaged_units=Decimal("2"),
    )
    assert calculate_osd_variance(qty) == Decimal("-2.00")


def test_clean_delivery_cannot_exceed_loaded_units():
    qty = ShipmentQuantities(
        tendered_units=Decimal("100"),
        loaded_units=Decimal("95"),
        delivered_units=Decimal("103"),
        damaged_units=Decimal("1"),
    )
    assert calculate_osd_variance(qty) == Decimal("-5.00")


def test_zero_tender_returns_clean_delivered_as_overage():
    qty = ShipmentQuantities(
        tendered_units=Decimal("0"),
        loaded_units=Decimal("0"),
        delivered_units=Decimal("4.50"),
    )
    assert calculate_osd_variance(qty) == Decimal("4.50")


def test_large_shipment_uses_capped_tolerance():
    qty = ShipmentQuantities(
        tendered_units=Decimal("1000"),
        loaded_units=Decimal("1000"),
        delivered_units=Decimal("998.50"),
    )
    assert calculate_osd_variance(qty) == Decimal("0.00")


def test_all_tendered_units_damaged_becomes_full_loss():
    qty = ShipmentQuantities(
        tendered_units=Decimal("8"),
        loaded_units=Decimal("8"),
        delivered_units=Decimal("8"),
        damaged_units=Decimal("8"),
    )
    assert calculate_osd_variance(qty) == Decimal("-8.00")


def test_loaded_more_than_tendered_is_rejected():
    qty = ShipmentQuantities(
        tendered_units=Decimal("10"),
        loaded_units=Decimal("11"),
        delivered_units=Decimal("10"),
    )
    with pytest.raises(ValueError):
        calculate_osd_variance(qty)


def test_custom_terms_can_tighten_tolerance():
    qty = ShipmentQuantities(
        tendered_units=Decimal("100"),
        loaded_units=Decimal("100"),
        delivered_units=Decimal("99.60"),
    )
    terms = VarianceTerms(absolute_tolerance_units=Decimal("0.25"), percent_tolerance=Decimal("0.0025"))
    assert calculate_osd_variance(qty, terms) == Decimal("-0.40")
