from decimal import Decimal

import pytest

from idling_fuel_burn import BurnRates, IdleEvent, calculate_idling_fuel_burn


def test_idle_within_grace_time_is_free():
    event = IdleEvent(idle_hours=Decimal("0.20"), ambient_temp_f=70)
    assert calculate_idling_fuel_burn(event) == Decimal("0.00")


def test_partial_tenth_hour_rounds_up_after_grace():
    event = IdleEvent(idle_hours=Decimal("0.21"), ambient_temp_f=70)
    assert calculate_idling_fuel_burn(event) == Decimal("0.08")


def test_engine_only_uses_normal_burn_rate():
    event = IdleEvent(idle_hours=Decimal("1.20"), ambient_temp_f=70)
    assert calculate_idling_fuel_burn(event) == Decimal("0.80")


def test_severe_cold_increases_engine_burn_rate():
    event = IdleEvent(idle_hours=Decimal("1.20"), ambient_temp_f=10)
    assert calculate_idling_fuel_burn(event) == Decimal("0.90")


def test_apu_applies_in_moderate_temperature_inclusive_boundary():
    event = IdleEvent(idle_hours=Decimal("1.20"), ambient_temp_f=35, has_apu=True)
    assert calculate_idling_fuel_burn(event) == Decimal("0.25")


def test_apu_does_not_apply_below_temperature_window():
    event = IdleEvent(idle_hours=Decimal("1.20"), ambient_temp_f=34, has_apu=True)
    assert calculate_idling_fuel_burn(event) == Decimal("0.80")


def test_reefer_tractor_overhead_adds_only_below_fifteen_f():
    event = IdleEvent(
        idle_hours=Decimal("1.20"),
        ambient_temp_f=14,
        reefer_powered_by_tractor=True,
    )
    assert calculate_idling_fuel_burn(event) == Decimal("1.00")


def test_reefer_does_not_change_apu_decision():
    event = IdleEvent(
        idle_hours=Decimal("2.20"),
        ambient_temp_f=60,
        has_apu=True,
        reefer_powered_by_tractor=True,
    )
    assert calculate_idling_fuel_burn(event) == Decimal("0.50")


def test_total_is_capped_per_event():
    event = IdleEvent(idle_hours=Decimal("40.20"), ambient_temp_f=100)
    assert calculate_idling_fuel_burn(event) == Decimal("30.00")


def test_negative_idle_hours_are_rejected():
    with pytest.raises(ValueError):
        calculate_idling_fuel_burn(IdleEvent(idle_hours=Decimal("-0.1"), ambient_temp_f=70))
