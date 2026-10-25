from decimal import Decimal

import pytest

from contract_margin_floor import MarginInputs, calculate_contract_margin_floor


def test_spot_short_haul_uses_14_percent_margin():
    inputs = MarginInputs(carrier_linehaul=Decimal("860.00"), miles=200)
    assert calculate_contract_margin_floor(inputs) == Decimal("1000.00")


def test_contract_medium_haul_uses_8_percent_margin():
    inputs = MarginInputs(carrier_linehaul=Decimal("920.00"), miles=500, is_contract=True)
    assert calculate_contract_margin_floor(inputs) == Decimal("1000.00")


def test_reefer_and_hazmat_raise_target_margin():
    inputs = MarginInputs(
        carrier_linehaul=Decimal("830.00"),
        miles=300,
        is_reefer=True,
        is_hazmat=True,
    )
    assert calculate_contract_margin_floor(inputs) == Decimal("976.47")


def test_same_day_short_haul_enforces_12_percent_minimum_for_contract():
    inputs = MarginInputs(
        carrier_linehaul=Decimal("880.00"),
        miles=150,
        is_contract=True,
        same_day=True,
    )
    assert calculate_contract_margin_floor(inputs) == Decimal("1000.00")


def test_missing_fuel_itemization_adds_7_percent_risk_buffer():
    inputs = MarginInputs(
        carrier_linehaul=Decimal("800.00"),
        miles=800,
        fuel_included_in_cost=False,
    )
    assert calculate_contract_margin_floor(inputs) == Decimal("951.11")


def test_urban_short_haul_adds_flat_handling_floor():
    inputs = MarginInputs(
        carrier_linehaul=Decimal("430.00"),
        miles=100,
        is_urban_delivery=True,
    )
    assert calculate_contract_margin_floor(inputs) == Decimal("625.00")


def test_cross_border_adds_flat_floor():
    inputs = MarginInputs(
        carrier_linehaul=Decimal("660.00"),
        miles=800,
        is_cross_border=True,
    )
    assert calculate_contract_margin_floor(inputs) == Decimal("983.33")


def test_absolute_minimum_applies_to_tiny_quotes():
    inputs = MarginInputs(carrier_linehaul=Decimal("100.00"), miles=50)
    assert calculate_contract_margin_floor(inputs) == Decimal("350.00")


def test_distance_band_boundaries_are_inclusive():
    short = MarginInputs(carrier_linehaul=Decimal("860.00"), miles=250)
    medium = MarginInputs(carrier_linehaul=Decimal("880.00"), miles=251)
    assert calculate_contract_margin_floor(short) == Decimal("1000.00")
    assert calculate_contract_margin_floor(medium) == Decimal("1000.00")


def test_negative_cost_is_rejected():
    with pytest.raises(ValueError):
        calculate_contract_margin_floor(MarginInputs(carrier_linehaul=Decimal("-1.00"), miles=100))
