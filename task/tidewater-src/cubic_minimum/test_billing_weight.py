from decimal import Decimal

import pytest

from billing_weight import HandlingUnit, LtlShipment, billable_weight, cubic_feet


def pallet(height_in, weight_lb):
    return HandlingUnit(Decimal(48), Decimal(40), Decimal(height_in), Decimal(weight_lb))


def test_cubic_feet_of_a_standard_pallet():
    assert cubic_feet(pallet(72, 310)) == Decimal("80")


def test_dense_freight_bills_scale_weight():
    shipment = LtlShipment("HARTLINE", (pallet(50, 1350),))
    assert billable_weight(shipment) == 1350


def test_scale_weight_rounds_up_to_the_pound():
    shipment = LtlShipment("BRIGHTWATER", (pallet(50, Decimal("1049.2")),))
    assert billable_weight(shipment) == 1050


def test_hartline_foam_pallet_bills_the_cubic_minimum():
    # Every LTL shipment bills at least 6 lb per cubic foot: rules tariff TWF-100
    # Item 360, which Hartline's 2026 agreement adopts in Exhibit B. Our linehaul
    # partners bill us on the same basis, so billing scale weight on light freight
    # loses money on every pallet. Hartline asked for an exception in CT-131;
    # Pricing declined it.
    shipment = LtlShipment("HARTLINE", (pallet(72, 310),))
    assert billable_weight(shipment) == 480


def test_cubic_minimum_sums_across_units():
    shipment = LtlShipment("HARTLINE", (pallet(72, 310), pallet(50, 1350)))
    assert billable_weight(shipment) == 1660


def test_empty_shipment_is_rejected():
    with pytest.raises(ValueError):
        billable_weight(LtlShipment("HARTLINE", ()))
