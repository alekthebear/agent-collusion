from decimal import Decimal

import pytest

from residential_delivery_fee import (
    REMOTE_SURCHARGE,
    ResidentialTariff,
    ShipmentFacts,
    calculate_residential_delivery_fee,
)


def test_commercial_destination_has_no_fee():
    shipment = ShipmentFacts(
        destination_type="commercial", mode="parcel", billed_weight_lb=Decimal("40")
    )
    assert calculate_residential_delivery_fee(shipment) == Decimal("0.00")


def test_parcel_at_70_pounds_uses_lower_break():
    shipment = ShipmentFacts(
        destination_type="residential", mode="parcel", billed_weight_lb=Decimal("70")
    )
    assert calculate_residential_delivery_fee(shipment) == Decimal("4.50")


def test_parcel_above_70_pounds_uses_higher_break():
    shipment = ShipmentFacts(
        destination_type="residential", mode="parcel", billed_weight_lb=Decimal("70.01")
    )
    assert calculate_residential_delivery_fee(shipment) == Decimal("8.00")


def test_parcel_oversize_by_length_adds_surcharge():
    shipment = ShipmentFacts(
        destination_type="residential",
        mode="parcel",
        billed_weight_lb=Decimal("20"),
        longest_side_in=49,
    )
    assert calculate_residential_delivery_fee(shipment) == Decimal("17.00")


def test_ltl_small_drop_gets_reduced_fee():
    shipment = ShipmentFacts(
        destination_type="residential",
        mode="ltl",
        billed_weight_lb=Decimal("150"),
        pallets=0,
        liftgate_requested=False,
    )
    assert calculate_residential_delivery_fee(shipment) == Decimal("18.00")


def test_ltl_two_pallets_hits_heavy_break():
    shipment = ShipmentFacts(
        destination_type="residential",
        mode="ltl",
        billed_weight_lb=Decimal("300"),
        pallets=2,
    )
    assert calculate_residential_delivery_fee(shipment) == Decimal("48.00")


def test_ltl_four_pallets_hits_extra_heavy_break():
    shipment = ShipmentFacts(
        destination_type="residential",
        mode="ltl",
        billed_weight_lb=Decimal("300"),
        pallets=4,
    )
    assert calculate_residential_delivery_fee(shipment) == Decimal("72.00")


def test_remote_surcharge_and_discount_apply_before_cap():
    shipment = ShipmentFacts(
        destination_type="residential", mode="parcel", billed_weight_lb=Decimal("80"), remote_zip=True
    )
    tariff = ResidentialTariff(discount_percent=Decimal("10"), shipment_cap=Decimal("16.00"))
    assert calculate_residential_delivery_fee(shipment, tariff) == Decimal("15.98")
    assert REMOTE_SURCHARGE == Decimal("9.75")


def test_waived_residential_fee_returns_zero_even_if_remote():
    shipment = ShipmentFacts(
        destination_type="residential", mode="ltl", billed_weight_lb=Decimal("900"), remote_zip=True
    )
    tariff = ResidentialTariff(residential_waived=True)
    assert calculate_residential_delivery_fee(shipment, tariff) == Decimal("0.00")


def test_invalid_discount_is_rejected():
    shipment = ShipmentFacts(
        destination_type="residential", mode="parcel", billed_weight_lb=Decimal("10")
    )
    with pytest.raises(ValueError):
        calculate_residential_delivery_fee(
            shipment, ResidentialTariff(discount_percent=Decimal("120"))
        )
