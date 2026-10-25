from decimal import Decimal

import pytest

from battery_replacement_cycle import (
    BatteryProfile,
    calculate_battery_replacement_cycle,
)


def profile(**overrides):
    base = dict(
        age_months=20,
        climate="mild",
        latest_resting_voltage=Decimal("12.52"),
        prior_resting_voltage=Decimal("12.52"),
        months_between_voltage_samples=3,
        jump_starts_last_90_days=0,
        corrosion_level="secure",
        tray_secured=True,
        starts_per_week=12,
    )
    base.update(overrides)
    return BatteryProfile(**base)


def test_baseline_profile_keeps_48_month_cycle():
    result = calculate_battery_replacement_cycle(profile())
    assert result.recommended_cycle_months == 48
    assert result.remaining_months == 28
    assert result.replace_now is False


def test_temperate_climate_shortens_cycle_by_three_months():
    result = calculate_battery_replacement_cycle(profile(climate="temperate"))
    assert result.recommended_cycle_months == 45
    assert result.remaining_months == 25
    assert result.replace_now is False


def test_voltage_decline_at_point_zero_two_per_month_gets_seven_month_penalty():
    result = calculate_battery_replacement_cycle(
        profile(latest_resting_voltage=Decimal("12.49"), prior_resting_voltage=Decimal("12.55"), months_between_voltage_samples=3)
    )
    assert result.recommended_cycle_months == 41
    assert result.remaining_months == 21
    assert result.replace_now is False


def test_latest_voltage_below_1180_replaces_now():
    result = calculate_battery_replacement_cycle(profile(latest_resting_voltage=Decimal("11.79")))
    assert result.recommended_cycle_months == 12
    assert result.remaining_months == 0
    assert result.replace_now is True


def test_low_voltage_with_two_recent_jump_starts_replaces_now():
    result = calculate_battery_replacement_cycle(
        profile(latest_resting_voltage=Decimal("11.95"), jump_starts_last_90_days=2)
    )
    assert result.recommended_cycle_months == 12
    assert result.remaining_months == 0
    assert result.replace_now is True


def test_heavy_corrosion_and_unsecured_tray_stack_penalties():
    result = calculate_battery_replacement_cycle(profile(corrosion_level="heavy", tray_secured=False))
    assert result.recommended_cycle_months == 38
    assert result.remaining_months == 18
    assert result.replace_now is False


def test_high_utilization_shortens_cycle_by_four_months():
    result = calculate_battery_replacement_cycle(profile(starts_per_week=26))
    assert result.recommended_cycle_months == 44
    assert result.remaining_months == 24
    assert result.replace_now is False


def test_light_use_extends_cycle_except_in_desert():
    mild = calculate_battery_replacement_cycle(profile(starts_per_week=4))
    desert = calculate_battery_replacement_cycle(profile(starts_per_week=4, climate="desert"))
    assert mild.recommended_cycle_months == 50
    assert mild.remaining_months == 30
    assert desert.recommended_cycle_months == 38
    assert desert.remaining_months == 18


def test_final_cycle_is_bounded_and_due_when_age_meets_cycle():
    result = calculate_battery_replacement_cycle(
        profile(
            age_months=12,
            climate="desert",
            latest_resting_voltage=Decimal("12.10"),
            prior_resting_voltage=Decimal("12.30"),
            months_between_voltage_samples=4,
            corrosion_level="heavy",
            tray_secured=False,
            starts_per_week=30,
        )
    )
    assert result.recommended_cycle_months == 12
    assert result.remaining_months == 0
    assert result.replace_now is True


def test_negative_age_is_rejected():
    with pytest.raises(ValueError):
        calculate_battery_replacement_cycle(profile(age_months=-1))
