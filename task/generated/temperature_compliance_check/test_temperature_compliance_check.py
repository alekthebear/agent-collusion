from decimal import Decimal

import pytest

from temperature_compliance_check import (
    PlannedSetpointRange,
    ProductTemperatureRequirements,
    evaluate_temperature_compliance_check,
)


def test_default_band_allows_range_inside_inclusive_limits():
    plan = PlannedSetpointRange(minimum_f=Decimal("32.5"), maximum_f=Decimal("39.5"))
    result = evaluate_temperature_compliance_check(plan)
    assert result.compliant is True
    assert result.effective_min_setpoint_f == Decimal("32.5")
    assert result.effective_max_setpoint_f == Decimal("39.5")
    assert result.reason_code == "compliant"


def test_below_minimum_limit_is_not_compliant():
    plan = PlannedSetpointRange(minimum_f=Decimal("32.4"), maximum_f=Decimal("39.0"))
    result = evaluate_temperature_compliance_check(plan)
    assert result.compliant is False
    assert result.reason_code == "below_min_limit"


def test_above_maximum_limit_is_not_compliant():
    plan = PlannedSetpointRange(minimum_f=Decimal("33.0"), maximum_f=Decimal("39.6"))
    result = evaluate_temperature_compliance_check(plan)
    assert result.compliant is False
    assert result.reason_code == "above_max_limit"


def test_temperature_sensitive_load_tightens_tolerance():
    req = ProductTemperatureRequirements(
        minimum_product_f=Decimal("34.0"),
        maximum_product_f=Decimal("38.0"),
        transit_hours=12,
        temperature_sensitive=True,
    )
    plan = PlannedSetpointRange(minimum_f=Decimal("33.0"), maximum_f=Decimal("39.0"))
    result = evaluate_temperature_compliance_check(plan, req)
    assert result.compliant is True
    assert result.effective_min_setpoint_f == Decimal("33.0")
    assert result.effective_max_setpoint_f == Decimal("39.0")


def test_sensitive_tolerance_has_minimum_floor_of_half_degree():
    req = ProductTemperatureRequirements(
        minimum_product_f=Decimal("34.0"),
        maximum_product_f=Decimal("38.0"),
        transit_hours=12,
        temperature_sensitive=True,
        control_tolerance_f=Decimal("0.3"),
    )
    plan = PlannedSetpointRange(minimum_f=Decimal("33.5"), maximum_f=Decimal("38.5"))
    result = evaluate_temperature_compliance_check(plan, req)
    assert result.compliant is True
    assert result.effective_min_setpoint_f == Decimal("33.5")
    assert result.effective_max_setpoint_f == Decimal("38.5")


def test_long_transit_over_24_hours_reduces_warm_limit():
    req = ProductTemperatureRequirements(
        minimum_product_f=Decimal("34.0"),
        maximum_product_f=Decimal("38.0"),
        transit_hours=30,
    )
    plan = PlannedSetpointRange(minimum_f=Decimal("32.5"), maximum_f=Decimal("39.0"))
    result = evaluate_temperature_compliance_check(plan, req)
    assert result.compliant is True
    assert result.effective_max_setpoint_f == Decimal("39.0")


def test_long_transit_over_48_hours_reduces_warm_limit_more():
    req = ProductTemperatureRequirements(
        minimum_product_f=Decimal("34.0"),
        maximum_product_f=Decimal("38.0"),
        transit_hours=49,
    )
    plan = PlannedSetpointRange(minimum_f=Decimal("32.5"), maximum_f=Decimal("38.6"))
    result = evaluate_temperature_compliance_check(plan, req)
    assert result.compliant is False
    assert result.effective_max_setpoint_f == Decimal("38.5")
    assert result.reason_code == "above_max_limit"


def test_frozen_load_caps_maximum_setpoint_at_ten_degrees():
    req = ProductTemperatureRequirements(
        minimum_product_f=Decimal("-10.0"),
        maximum_product_f=Decimal("9.0"),
        transit_hours=10,
        frozen=True,
    )
    plan = PlannedSetpointRange(minimum_f=Decimal("-11.5"), maximum_f=Decimal("10.0"))
    result = evaluate_temperature_compliance_check(plan, req)
    assert result.compliant is True
    assert result.effective_max_setpoint_f == Decimal("10.0")


def test_tolerance_is_rounded_half_up_before_limit_comparison():
    req = ProductTemperatureRequirements(
        minimum_product_f=Decimal("34.0"),
        maximum_product_f=Decimal("38.0"),
        transit_hours=0,
        control_tolerance_f=Decimal("1.44"),
    )
    plan = PlannedSetpointRange(minimum_f=Decimal("32.6"), maximum_f=Decimal("39.4"))
    result = evaluate_temperature_compliance_check(plan, req)
    assert result.compliant is True
    assert result.effective_min_setpoint_f == Decimal("32.6")
    assert result.effective_max_setpoint_f == Decimal("39.4")


def test_invalid_planned_range_is_rejected():
    with pytest.raises(ValueError):
        evaluate_temperature_compliance_check(
            PlannedSetpointRange(minimum_f=Decimal("40.0"), maximum_f=Decimal("39.0"))
        )
