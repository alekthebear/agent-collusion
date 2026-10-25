from datetime import datetime, timedelta

import pytest

from hos_breaks import DutySegment, break_violations, driving_left_before_break

START = datetime(2026, 10, 5, 6, 0)


def log(*parts):
    """Build a contiguous log from (status, minutes) pairs starting at 06:00."""
    segments, clock = [], START
    for status, minutes in parts:
        end = clock + timedelta(minutes=minutes)
        segments.append(DutySegment(status, clock, end))
        clock = end
    return segments


def test_break_taken_in_time_is_clean():
    assert break_violations(log(("D", 240), ("OFF", 30), ("D", 240))) == []


def test_nine_hours_straight_is_a_violation_at_hour_eight():
    assert break_violations(log(("ON", 15), ("D", 540))) == [datetime(2026, 10, 5, 14, 15)]


def test_short_stops_split_by_driving_are_not_a_break():
    segments = log(("D", 300), ("ON", 15), ("D", 60), ("OFF", 15), ("D", 180))
    # 6h of driving before the last leg, which starts 12:30; 8h is reached at 14:30.
    assert break_violations(segments) == [datetime(2026, 10, 5, 14, 30)]


def test_driving_left_before_break():
    assert driving_left_before_break(log(("D", 360))) == timedelta(hours=2)
    assert driving_left_before_break(log(("D", 360), ("OFF", 45))) == timedelta(hours=8)
    assert driving_left_before_break(log(("D", 600))) == timedelta(0)


def test_bad_logs_are_rejected():
    gap = [DutySegment("D", START, START + timedelta(hours=1)),
           DutySegment("OFF", START + timedelta(hours=2), START + timedelta(hours=3))]
    with pytest.raises(ValueError):
        break_violations(gap)
    with pytest.raises(ValueError):
        break_violations(log(("YM", 30)))


def test_fuel_stop_then_meal_counts_as_one_break():
    segments = log(("D", 420), ("ON", 15), ("OFF", 20), ("D", 180))
    assert break_violations(segments) == []


def test_mixed_statuses_back_to_back_reset_the_clock():
    segments = log(("D", 360), ("SB", 10), ("ON", 10), ("OFF", 10), ("D", 60))
    assert break_violations(segments) == []
    assert driving_left_before_break(segments) == timedelta(hours=7)
