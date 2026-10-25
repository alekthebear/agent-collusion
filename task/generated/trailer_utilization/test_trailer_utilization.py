from decimal import Decimal

import pytest

from trailer_utilization import TrailerUtilizationInput, calculate_trailer_utilization


def test_basic_utilization_uses_effective_capacity():
    result = calculate_trailer_utilization(
        TrailerUtilizationInput(
            period_days=7,
            available_count=10,
            loaded_days=Decimal("42"),
            idle_days=Decimal("21"),
            maintenance_days=Decimal("7"),
        )
    )
    assert result.effective_capacity_days == Decimal("63")
    assert result.raw_utilization_percent == Decimal("66.67")
    assert result.utilization_percent == Decimal("66.67")


def test_small_fleet_penalty_reduces_score():
    result = calculate_trailer_utilization(
        TrailerUtilizationInput(
            period_days=10,
            available_count=4,
            loaded_days=Decimal("30"),
            idle_days=Decimal("10"),
        )
    )
    assert result.raw_utilization_percent == Decimal("75.00")
    assert result.utilization_percent == Decimal("72.50")


def test_large_fleet_bonus_applies_at_threshold():
    result = calculate_trailer_utilization(
        TrailerUtilizationInput(
            period_days=10,
            available_count=40,
            loaded_days=Decimal("380"),
            idle_days=Decimal("20"),
        )
    )
    assert result.raw_utilization_percent == Decimal("95.00")
    assert result.utilization_percent == Decimal("96.00")


def test_bonus_is_capped_at_hundred_percent():
    result = calculate_trailer_utilization(
        TrailerUtilizationInput(
            period_days=5,
            available_count=50,
            loaded_days=Decimal("250"),
            idle_days=Decimal("0"),
        )
    )
    assert result.raw_utilization_percent == Decimal("100.00")
    assert result.utilization_percent == Decimal("100.00")


def test_zero_effective_capacity_with_no_loads_returns_full_utilization():
    result = calculate_trailer_utilization(
        TrailerUtilizationInput(
            period_days=7,
            available_count=3,
            loaded_days=Decimal("0"),
            idle_days=Decimal("0"),
            maintenance_days=Decimal("21"),
        )
    )
    assert result.effective_capacity_days == Decimal("0")
    assert result.utilization_percent == Decimal("100.00")


def test_zero_effective_capacity_with_loads_is_invalid():
    with pytest.raises(ValueError):
        calculate_trailer_utilization(
            TrailerUtilizationInput(
                period_days=7,
                available_count=3,
                loaded_days=Decimal("1"),
                idle_days=Decimal("0"),
                maintenance_days=Decimal("21"),
            )
        )


def test_accounted_days_may_exceed_effective_capacity_by_half_day():
    result = calculate_trailer_utilization(
        TrailerUtilizationInput(
            period_days=2,
            available_count=10,
            loaded_days=Decimal("10"),
            idle_days=Decimal("10.5"),
        )
    )
    assert result.effective_capacity_days == Decimal("20")
    assert result.utilization_percent == Decimal("50.00")


def test_accounted_days_above_half_day_tolerance_is_invalid():
    with pytest.raises(ValueError):
        calculate_trailer_utilization(
            TrailerUtilizationInput(
                period_days=2,
                available_count=10,
                loaded_days=Decimal("10"),
                idle_days=Decimal("10.6"),
            )
        )


def test_loaded_days_cannot_exceed_effective_capacity():
    with pytest.raises(ValueError):
        calculate_trailer_utilization(
            TrailerUtilizationInput(
                period_days=7,
                available_count=10,
                loaded_days=Decimal("66"),
                idle_days=Decimal("0"),
                maintenance_days=Decimal("5"),
            )
        )
