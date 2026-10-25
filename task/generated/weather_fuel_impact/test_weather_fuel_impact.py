from decimal import Decimal

import pytest

from weather_fuel_impact import (
    TripAssumptions,
    WeatherProfile,
    calculate_weather_fuel_impact,
)


def test_baseline_mild_conditions_have_no_uplift():
    weather = WeatherProfile(temperature_f=70, wind_mph=5)
    assert calculate_weather_fuel_impact(weather) == Decimal("0.00")


def test_freezing_boundary_is_still_no_temperature_penalty():
    weather = WeatherProfile(temperature_f=32, wind_mph=0)
    assert calculate_weather_fuel_impact(weather) == Decimal("0.00")


def test_subfreezing_temperature_adds_winter_penalty():
    weather = WeatherProfile(temperature_f=31, wind_mph=0)
    assert calculate_weather_fuel_impact(weather) == Decimal("1.75")


def test_extreme_heat_and_reefer_and_rolling_terrain_stack():
    weather = WeatherProfile(temperature_f=96, wind_mph=0)
    trip = TripAssumptions(terrain="rolling", equipment_type="reefer")
    assert calculate_weather_fuel_impact(weather, trip) == Decimal("3.25")


def test_crosswind_is_lower_than_headwind_in_same_band():
    weather = WeatherProfile(temperature_f=70, wind_mph=25, wind_direction="cross")
    assert calculate_weather_fuel_impact(weather) == Decimal("1.00")


def test_tailwind_never_creates_a_credit_or_charge():
    weather = WeatherProfile(temperature_f=70, wind_mph=45, wind_direction="tail")
    assert calculate_weather_fuel_impact(weather) == Decimal("0.00")


def test_trace_precipitation_is_ignored():
    weather = WeatherProfile(
        temperature_f=70,
        wind_mph=0,
        precipitation_in_per_hr=Decimal("0.009"),
        precipitation_type="rain",
    )
    assert calculate_weather_fuel_impact(weather) == Decimal("0.00")


def test_snow_penalty_and_severe_combined_condition_surcharge_apply():
    weather = WeatherProfile(
        temperature_f=20,
        wind_mph=30,
        wind_direction="head",
        precipitation_in_per_hr=Decimal("0.10"),
        precipitation_type="snow",
    )
    trip = TripAssumptions(terrain="hilly", equipment_type="day_cab")
    assert calculate_weather_fuel_impact(weather, trip) == Decimal("10.15")


def test_total_is_below_cap_for_severe_but_not_extreme_case():
    weather = WeatherProfile(
        temperature_f=-10,
        wind_mph=50,
        wind_direction="head",
        precipitation_in_per_hr=Decimal("0.20"),
        precipitation_type="snow",
    )
    trip = TripAssumptions(terrain="mountain", equipment_type="reefer")
    assert calculate_weather_fuel_impact(weather, trip) == Decimal("16.25")


def test_invalid_none_precipitation_with_rate_is_rejected():
    weather = WeatherProfile(
        temperature_f=70,
        wind_mph=0,
        precipitation_in_per_hr=Decimal("0.01"),
        precipitation_type="none",
    )
    with pytest.raises(ValueError):
        calculate_weather_fuel_impact(weather)
