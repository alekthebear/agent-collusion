from datetime import date, datetime, time

import pytest

from concealed_damage_window import (
    CustomerBusinessCalendar,
    DeliveryRecord,
    calculate_concealed_damage_window,
)


def at(day, hour=9, minute=0, second=0):
    return datetime(2026, 4, day, hour, minute, second)


def test_standard_window_allows_five_business_days_including_delivery_day():
    record = DeliveryRecord(delivered_at=at(6, 10), notice_at=at(10, 12))
    timely, deadline = calculate_concealed_damage_window(record)
    assert deadline == at(10, 23, 59, 59)
    assert timely is True


def test_notice_one_second_after_deadline_is_late():
    record = DeliveryRecord(delivered_at=at(6, 10), notice_at=at(11, 0, 0, 0))
    timely, deadline = calculate_concealed_damage_window(record)
    assert deadline == at(10, 23, 59, 59)
    assert timely is False


def test_weekend_days_are_skipped_in_count():
    record = DeliveryRecord(delivered_at=at(9, 11), notice_at=at(15, 8))
    timely, deadline = calculate_concealed_damage_window(record)
    assert deadline == at(15, 23, 59, 59)
    assert timely is True


def test_holiday_is_skipped_like_a_non_business_day():
    calendar = CustomerBusinessCalendar(holidays=(date(2026, 4, 13),))
    record = DeliveryRecord(delivered_at=at(9, 11), notice_at=at(16, 8))
    timely, deadline = calculate_concealed_damage_window(record, calendar)
    assert deadline == at(16, 23, 59, 59)
    assert timely is True


def test_food_grade_uses_stricter_three_business_day_limit():
    record = DeliveryRecord(delivered_at=at(6, 10), notice_at=at(8, 14), service_level="food_grade")
    timely, deadline = calculate_concealed_damage_window(record)
    assert deadline == at(8, 23, 59, 59)
    assert timely is True


def test_white_glove_adds_one_business_day():
    record = DeliveryRecord(delivered_at=at(6, 10), notice_at=at(13, 15), service_level="white_glove")
    timely, deadline = calculate_concealed_damage_window(record)
    assert deadline == at(13, 23, 59, 59)
    assert timely is True


def test_delivery_after_dock_close_starts_count_next_day():
    record = DeliveryRecord(delivered_at=at(6, 18), notice_at=at(13, 10))
    timely, deadline = calculate_concealed_damage_window(record)
    assert deadline == at(13, 23, 59, 59)
    assert timely is True


def test_saturday_can_be_enabled_as_business_day():
    calendar = CustomerBusinessCalendar(saturday_is_business_day=True)
    record = DeliveryRecord(delivered_at=at(9, 11), notice_at=at(14, 9))
    timely, deadline = calculate_concealed_damage_window(record, calendar)
    assert deadline == at(14, 23, 59, 59)
    assert timely is True


def test_notice_before_delivery_is_rejected():
    record = DeliveryRecord(delivered_at=at(6, 10), notice_at=at(5, 12))
    with pytest.raises(ValueError):
        calculate_concealed_damage_window(record)
