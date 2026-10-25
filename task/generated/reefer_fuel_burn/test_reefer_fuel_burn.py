from decimal import Decimal

import pytest

from reefer_fuel_burn import FuelBurnResult, ReeferLoad, calculate_reefer_fuel_burn


def test_continuous_chilled_uses_full_hours_and_high_spread_band():
    load = ReeferLoad(setpoint_f=34, ambient_f=90, mode="continuous", run_hours=Decimal("10"))
    result = calculate_reefer_fuel_burn(load)
    assert result == FuelBurnResult(billed_engine_hours=Decimal("10"), gallons_burned=Decimal("9.00"))


def test_frozen_boundary_at_28_gets_frozen_rate_and_mid_defrost():
    load = ReeferLoad(setpoint_f=28, ambient_f=60, mode="continuous", run_hours=Decimal("5"))
    result = calculate_reefer_fuel_burn(load)
    assert result == FuelBurnResult(billed_engine_hours=Decimal("5"), gallons_burned=Decimal("6.25"))


def test_start_stop_short_window_bills_minimum_engine_hours():
    load = ReeferLoad(setpoint_f=35, ambient_f=55, mode="start_stop", run_hours=Decimal("1.5"))
    result = calculate_reefer_fuel_burn(load)
    assert result == FuelBurnResult(billed_engine_hours=Decimal("1.2"), gallons_burned=Decimal("0.70"))


def test_start_stop_long_window_uses_duty_factor():
    load = ReeferLoad(setpoint_f=36, ambient_f=70, mode="start_stop", run_hours=Decimal("10"))
    result = calculate_reefer_fuel_burn(load)
    assert result.billed_engine_hours == Decimal("7.20")
    assert result.gallons_burned == Decimal("4.68")


def test_negative_spread_gets_low_ambient_factor():
    load = ReeferLoad(setpoint_f=34, ambient_f=20, mode="continuous", run_hours=Decimal("10"))
    result = calculate_reefer_fuel_burn(load)
    assert result.gallons_burned == Decimal("6.62")


def test_door_open_surcharge_applies_only_above_45_minutes():
    base = ReeferLoad(setpoint_f=34, ambient_f=70, mode="continuous", run_hours=Decimal("10"), door_open_minutes=45)
    extra = ReeferLoad(setpoint_f=34, ambient_f=70, mode="continuous", run_hours=Decimal("10"), door_open_minutes=46)
    assert calculate_reefer_fuel_burn(base).gallons_burned == Decimal("8.06")
    assert calculate_reefer_fuel_burn(extra).gallons_burned == Decimal("8.71")


def test_altitude_surcharge_applies_only_above_5000_feet():
    low = ReeferLoad(setpoint_f=34, ambient_f=70, mode="continuous", run_hours=Decimal("10"), altitude_feet=5000)
    high = ReeferLoad(setpoint_f=34, ambient_f=70, mode="continuous", run_hours=Decimal("10"), altitude_feet=5001)
    assert calculate_reefer_fuel_burn(low).gallons_burned == Decimal("8.06")
    assert calculate_reefer_fuel_burn(high).gallons_burned == Decimal("8.47")


def test_high_efficiency_family_uses_lower_table():
    load = ReeferLoad(setpoint_f=34, ambient_f=70, mode="continuous", run_hours=Decimal("10"), trailer_family="high_efficiency")
    result = calculate_reefer_fuel_burn(load)
    assert result.gallons_burned == Decimal("7.17")


def test_zero_hours_returns_zero_without_minimums_or_defrost():
    load = ReeferLoad(setpoint_f=0, ambient_f=95, mode="start_stop", run_hours=Decimal("0"))
    result = calculate_reefer_fuel_burn(load)
    assert result == FuelBurnResult(billed_engine_hours=Decimal("0.0"), gallons_burned=Decimal("0.00"))


def test_negative_run_hours_is_rejected():
    with pytest.raises(ValueError):
        calculate_reefer_fuel_burn(ReeferLoad(setpoint_f=34, ambient_f=70, mode="continuous", run_hours=Decimal("-1")))
