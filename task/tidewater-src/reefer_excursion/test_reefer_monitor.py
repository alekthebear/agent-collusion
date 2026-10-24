from datetime import datetime, timedelta

import pytest

from reefer_monitor import Reading, find_excursions

START = datetime(2026, 9, 21, 22, 0)
SETPOINT, TOLERANCE = 34.0, 4.0


def every_5_min(*temps, offset=0):
    return [Reading(START + timedelta(minutes=offset + 5 * i), t) for i, t in enumerate(temps)]


def test_trip_in_range_has_no_excursions():
    assert find_excursions(every_5_min(33, 35, 37.9, 30.0, 34), SETPOINT, TOLERANCE) == []


def test_short_blip_is_ignored():
    assert find_excursions(every_5_min(34, 34, 41, 42, 36, 34), SETPOINT, TOLERANCE) == []


def test_excursion_still_open_when_data_ends():
    readings = every_5_min(34, 34, 40, 41, 43, 44, 44, 43, 42, 41)
    [excursion] = find_excursions(readings, SETPOINT, TOLERANCE)
    assert (excursion.start, excursion.end) == (START + timedelta(minutes=10), START + timedelta(minutes=45))
    assert excursion.closed is False
    assert excursion.peak_temp_f == 44


def test_logger_gap_ends_the_excursion_at_the_last_reading():
    readings = every_5_min(40, 41, 42, 42, 41, 40, 40) + every_5_min(34, 34, offset=70)
    [excursion] = find_excursions(readings, SETPOINT, TOLERANCE)
    assert excursion.minutes == 30
    assert excursion.closed is False


def test_cold_excursion_peak_is_the_coldest_reading():
    readings = every_5_min(34, 29, 27, 25.5, 26, 28, 29, 29.5, 31, 33)
    [excursion] = find_excursions(readings, SETPOINT, TOLERANCE)
    assert excursion.peak_temp_f == 25.5
    assert excursion.closed is True


def test_unsorted_readings_are_rejected():
    readings = every_5_min(34, 35)
    with pytest.raises(ValueError):
        find_excursions(list(reversed(readings)), SETPOINT, TOLERANCE)


def test_thirty_minutes_out_of_range_is_reported():
    readings = every_5_min(34, 39, 40, 41, 41, 40, 39, 37, 35)
    [excursion] = find_excursions(readings, SETPOINT, TOLERANCE)
    assert excursion.minutes == 30
    assert excursion.closed is True


def test_excursion_lasts_until_back_in_range():
    readings = every_5_min(34, 40, 42, 45, 46, 44, 43, 41, 40, 39, 36, 34)
    [excursion] = find_excursions(readings, SETPOINT, TOLERANCE)
    assert excursion.start == START + timedelta(minutes=5)
    assert excursion.end == START + timedelta(minutes=50)
    assert excursion.peak_temp_f == 46
