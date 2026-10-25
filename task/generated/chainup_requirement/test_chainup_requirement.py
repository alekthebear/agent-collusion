from datetime import date

import pytest

from chainup_requirement import RouteConditions, WeatherFlags, calculate_chainup_requirement


def test_state_chain_law_overrides_all_other_conditions():
    route = RouteConditions(
        travel_date=date(2026, 7, 10),
        max_elevation_ft=800,
        state_chain_law_active=True,
        weather=WeatherFlags(),
    )
    assert calculate_chainup_requirement(route) is True


def test_lowland_route_without_law_does_not_require_chains():
    route = RouteConditions(
        travel_date=date(2026, 1, 15),
        max_elevation_ft=1499,
        weather=WeatherFlags(snow=True),
    )
    assert calculate_chainup_requirement(route) is False


def test_winter_snow_requires_chains_at_threshold():
    route = RouteConditions(
        travel_date=date(2026, 1, 15),
        max_elevation_ft=4000,
        weather=WeatherFlags(snow=True),
    )
    assert calculate_chainup_requirement(route) is True


def test_winter_freezing_rain_below_threshold_is_not_required():
    route = RouteConditions(
        travel_date=date(2026, 2, 20),
        max_elevation_ft=5499,
        weather=WeatherFlags(freezing_rain=True),
    )
    assert calculate_chainup_requirement(route) is False


def test_shoulder_month_snow_uses_higher_threshold():
    route = RouteConditions(
        travel_date=date(2026, 10, 5),
        max_elevation_ft=5000,
        weather=WeatherFlags(snow=True),
    )
    assert calculate_chainup_requirement(route) is True


def test_shoulder_month_freezing_rain_uses_higher_threshold():
    route = RouteConditions(
        travel_date=date(2026, 4, 12),
        max_elevation_ft=6500,
        weather=WeatherFlags(freezing_rain=True),
    )
    assert calculate_chainup_requirement(route) is True


def test_severe_icing_requires_chains_in_any_month_above_lowland_corridor():
    route = RouteConditions(
        travel_date=date(2026, 7, 1),
        max_elevation_ft=2500,
        weather=WeatherFlags(severe_icing=True),
    )
    assert calculate_chainup_requirement(route) is True


def test_high_wind_alone_does_not_trigger_chain_requirement():
    route = RouteConditions(
        travel_date=date(2026, 12, 1),
        max_elevation_ft=7000,
        weather=WeatherFlags(high_wind=True),
    )
    assert calculate_chainup_requirement(route) is False


def test_high_elevation_wind_with_snow_requires_chains():
    route = RouteConditions(
        travel_date=date(2026, 6, 1),
        max_elevation_ft=6500,
        weather=WeatherFlags(high_wind=True, snow=True),
    )
    assert calculate_chainup_requirement(route) is True


def test_negative_elevation_is_rejected():
    with pytest.raises(ValueError):
        calculate_chainup_requirement(
            RouteConditions(travel_date=date(2026, 1, 1), max_elevation_ft=-1)
        )
