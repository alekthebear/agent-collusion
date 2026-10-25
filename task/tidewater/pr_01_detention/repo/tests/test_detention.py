from datetime import datetime
from decimal import Decimal

import pytest

from detention import DetentionTerms, StopTimes, detention_charge


def at(hour, minute=0):
    return datetime(2026, 3, 2, hour, minute)


def test_released_within_free_time_is_free():
    stop = StopTimes(arrived=at(8), departed=at(9, 45), appointment=at(8))
    assert detention_charge(stop) == Decimal("0.00")


def test_partial_quarter_hour_bills_a_full_increment():
    stop = StopTimes(arrived=at(8), departed=at(10, 20), appointment=at(8))
    assert detention_charge(stop) == Decimal("37.50")


def test_late_driver_starts_clock_at_check_in():
    stop = StopTimes(arrived=at(9), departed=at(12), appointment=at(8))
    assert detention_charge(stop) == Decimal("75.00")


def test_fcfs_stop_starts_clock_at_check_in():
    stop = StopTimes(arrived=at(13), departed=at(16, 30))
    assert detention_charge(stop) == Decimal("112.50")


def test_charge_is_capped_per_stop():
    stop = StopTimes(arrived=at(6), departed=at(20), appointment=at(6))
    assert detention_charge(stop) == Decimal("600.00")
    uncapped = DetentionTerms(stop_cap=None)
    assert detention_charge(stop, uncapped) == Decimal("900.00")


def test_early_arrival_waits_on_carrier_time():
    stop = StopTimes(arrived=at(7), departed=at(11), appointment=at(8))
    assert detention_charge(stop) == Decimal("75.00")


def test_early_arrival_released_inside_free_time():
    stop = StopTimes(arrived=at(6, 30), departed=at(9, 50), appointment=at(8))
    assert detention_charge(stop) == Decimal("0.00")


def test_departure_before_arrival_is_rejected():
    with pytest.raises(ValueError):
        detention_charge(StopTimes(arrived=at(10), departed=at(9)))
