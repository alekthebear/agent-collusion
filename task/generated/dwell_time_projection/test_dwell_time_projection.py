from decimal import Decimal

import pytest

from dwell_time_projection import (
    DwellProjection,
    FacilityBenchmark,
    StopProfile,
    calculate_dwell_time_projection,
)


def bench(minutes=120):
    return FacilityBenchmark(facility_code="DAL01", benchmark_minutes=minutes)


def test_strict_appointment_reduces_by_ten_percent_of_benchmark():
    stop = StopProfile("strict", "general", "live_unload", 20)
    result = calculate_dwell_time_projection(bench(120), stop)
    assert result == DwellProjection(projected_minutes=130, benchmark_minutes=120, adjustment_minutes=10)


def test_window_appointment_adds_fifteen_minutes():
    stop = StopProfile("window", "general", "palletized", 20)
    result = calculate_dwell_time_projection(bench(120), stop)
    assert result.projected_minutes == 120
    assert result.adjustment_minutes == 0


def test_fcfs_frozen_floor_loaded_gets_extra_volatility_bump():
    stop = StopProfile("fcfs", "frozen", "floor_loaded", 20)
    result = calculate_dwell_time_projection(bench(120), stop)
    assert result.projected_minutes == 270
    assert result.adjustment_minutes == 150


def test_strict_produce_drop_hook_gets_special_fast_path_but_not_below_drop_hook_minimum():
    stop = StopProfile("strict", "produce", "drop_hook", 20)
    result = calculate_dwell_time_projection(bench(60), stop)
    assert result.projected_minutes == 30
    assert result.adjustment_minutes == -30


def test_started_tens_above_forty_handling_units_are_added():
    stop = StopProfile("window", "general", "palletized", 41)
    result = calculate_dwell_time_projection(bench(100), stop)
    assert result.projected_minutes == 110
    assert result.adjustment_minutes == 10


def test_fewer_than_six_handling_units_reduce_ten_minutes():
    stop = StopProfile("window", "general", "live_unload", 5)
    result = calculate_dwell_time_projection(bench(100), stop)
    assert result.projected_minutes == 125
    assert result.adjustment_minutes == 25


def test_team_driver_reduction_does_not_apply_to_hazmat():
    stop = StopProfile("window", "hazmat", "palletized", 20, team_driver=True)
    result = calculate_dwell_time_projection(bench(100), stop)
    assert result.projected_minutes == 150
    assert result.adjustment_minutes == 50


def test_driver_assist_and_team_driver_stack_for_non_hazmat():
    stop = StopProfile("window", "general", "palletized", 20, driver_assist=True, team_driver=True)
    result = calculate_dwell_time_projection(bench(100), stop)
    assert result.projected_minutes == 115
    assert result.adjustment_minutes == 15


def test_projection_is_capped_at_fourteen_hours():
    stop = StopProfile("fcfs", "hazmat", "floor_loaded", 130, driver_assist=True)
    result = calculate_dwell_time_projection(bench(720), stop)
    assert result.projected_minutes == 840
    assert result.adjustment_minutes == 120


def test_invalid_benchmark_range_is_rejected():
    stop = StopProfile("window", "general", "palletized", 10)
    with pytest.raises(ValueError):
        calculate_dwell_time_projection(FacilityBenchmark("DAL01", 10), stop)
