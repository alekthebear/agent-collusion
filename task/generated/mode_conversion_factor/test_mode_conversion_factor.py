from decimal import Decimal

import pytest

from mode_conversion_factor import (
    ConversionRequest,
    ConversionTerms,
    calculate_mode_conversion_factor,
)


def test_base_factor_is_used_when_no_adjustments_apply():
    req = ConversionRequest(
        source_mode="truckload",
        target_mode="drayage",
        weight_lb=12000,
        distance_miles=300,
        stops=2,
    )
    assert calculate_mode_conversion_factor(req) == Decimal("0.7600")


def test_small_shipment_to_ltl_gets_weight_uplift():
    req = ConversionRequest(
        source_mode="truckload",
        target_mode="ltl",
        weight_lb=4999,
        distance_miles=300,
        stops=2,
    )
    assert calculate_mode_conversion_factor(req) == Decimal("1.2600")


def test_heavy_shipment_to_ltl_gets_weight_discount():
    req = ConversionRequest(
        source_mode="truckload",
        target_mode="ltl",
        weight_lb=20001,
        distance_miles=300,
        stops=2,
    )
    assert calculate_mode_conversion_factor(req) == Decimal("1.1300")


def test_long_haul_to_truckload_gets_distance_discount():
    req = ConversionRequest(
        source_mode="ltl",
        target_mode="truckload",
        weight_lb=10000,
        distance_miles=1000,
        stops=2,
    )
    assert calculate_mode_conversion_factor(req) == Decimal("0.8200")


def test_residential_only_affects_ltl_target():
    req = ConversionRequest(
        source_mode="flatbed",
        target_mode="ltl",
        weight_lb=12000,
        distance_miles=250,
        stops=2,
        residential=True,
    )
    assert calculate_mode_conversion_factor(req) == Decimal("1.1350")


def test_hazmat_to_drayage_uses_smaller_uplift():
    req = ConversionRequest(
        source_mode="truckload",
        target_mode="drayage",
        weight_lb=12000,
        distance_miles=200,
        stops=2,
        hazmat=True,
    )
    assert calculate_mode_conversion_factor(req) == Decimal("0.7700")


def test_short_drayage_override_applies_at_boundary():
    req = ConversionRequest(
        source_mode="drayage",
        target_mode="truckload",
        weight_lb=15000,
        distance_miles=25,
        stops=2,
    )
    assert calculate_mode_conversion_factor(req) == Decimal("0.5800")


def test_stop_surcharge_is_capped():
    req = ConversionRequest(
        source_mode="ltl",
        target_mode="flatbed",
        weight_lb=15000,
        distance_miles=400,
        stops=8,
    )
    assert calculate_mode_conversion_factor(req) == Decimal("1.1100")


def test_cross_border_and_overdimensional_stack_on_flatbed():
    req = ConversionRequest(
        source_mode="truckload",
        target_mode="flatbed",
        weight_lb=32000,
        distance_miles=1200,
        stops=3,
        cross_border=True,
        overdimensional=True,
    )
    assert calculate_mode_conversion_factor(req) == Decimal("1.2500")


def test_invalid_same_mode_is_rejected():
    req = ConversionRequest(
        source_mode="truckload",
        target_mode="truckload",
        weight_lb=10000,
        distance_miles=100,
    )
    with pytest.raises(ValueError):
        calculate_mode_conversion_factor(req)
