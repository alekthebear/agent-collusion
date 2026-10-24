from datetime import date, datetime, time, timezone

import pytest

from delivery_window import (
    EARLY, LATE, ON_TIME, latest_departure, receiving_window, slack_minutes, window_minutes, window_status,
)

NEWARK = "America/New_York"


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_day_window_length_and_slack():
    window = receiving_window(date(2026, 10, 6), time(8), time(16), NEWARK)
    assert window_minutes(window) == 480
    # 14:00 EDT, two hours before close
    assert slack_minutes(utc(2026, 10, 6, 18, 0), window) == 120


def test_night_window_closes_the_next_morning():
    window = receiving_window(date(2026, 10, 6), time(22), time(6), NEWARK)
    assert window.closes.date() == date(2026, 10, 7)
    assert window_minutes(window) == 480


def test_status_early_on_time_and_late():
    window = receiving_window(date(2026, 10, 6), time(8), time(16), NEWARK)
    assert window_status(utc(2026, 10, 6, 11, 0), window) == EARLY
    assert window_status(utc(2026, 10, 6, 15, 0), window) == ON_TIME
    assert window_status(utc(2026, 10, 6, 20, 30), window) == LATE
    with pytest.raises(ValueError):
        window_status(datetime(2026, 10, 6, 12, 0), window)


def test_latest_departure_is_in_utc():
    window = receiving_window(date(2026, 10, 6), time(8), time(16), NEWARK)
    assert latest_departure(window, 90) == utc(2026, 10, 6, 18, 30)


def test_night_window_over_fall_back_is_nine_hours():
    window = receiving_window(date(2026, 10, 31), time(22), time(6), NEWARK)
    assert window_minutes(window) == 540


def test_slack_over_fall_back_counts_the_extra_hour():
    window = receiving_window(date(2026, 10, 31), time(22), time(6), NEWARK)
    # 01:00 EDT; the window closes at 06:00 EST, six real hours later.
    assert slack_minutes(utc(2026, 11, 1, 5, 0), window) == 360


def test_slack_over_spring_forward_loses_an_hour():
    window = receiving_window(date(2026, 3, 7), time(22), time(6), NEWARK)
    # 01:30 EST; the window closes at 06:00 EDT, three and a half real hours later.
    assert slack_minutes(utc(2026, 3, 8, 6, 30), window) == 210
    assert window_minutes(window) == 420
