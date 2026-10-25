from datetime import date, datetime
from decimal import Decimal

import pytest

from after_hours_service_fee import (
    AfterHoursTerms,
    FacilityCalendar,
    ServiceRequest,
    calculate_after_hours_service_fee,
)


def dt(day, hour, minute=0):
    return datetime(2026, 7, day, hour, minute)


def test_inside_business_hours_is_free():
    request = ServiceRequest(appointment_start=dt(6, 9), appointment_end=dt(6, 10))
    assert calculate_after_hours_service_fee(request) == Decimal("0.00")


def test_opening_time_is_inside_business_hours():
    request = ServiceRequest(appointment_start=dt(6, 8), appointment_end=dt(6, 8, 30))
    assert calculate_after_hours_service_fee(request) == Decimal("0.00")


def test_closing_time_start_is_after_hours_shoulder_fee():
    request = ServiceRequest(appointment_start=dt(6, 17), appointment_end=dt(6, 18))
    assert calculate_after_hours_service_fee(request) == Decimal("125.00")


def test_weekday_more_than_two_hours_before_open_is_overnight_fee():
    request = ServiceRequest(appointment_start=dt(6, 5, 59), appointment_end=dt(6, 6, 30))
    assert calculate_after_hours_service_fee(request) == Decimal("225.00")


def test_exactly_two_hours_before_open_is_shoulder_fee():
    request = ServiceRequest(appointment_start=dt(6, 6), appointment_end=dt(6, 7))
    assert calculate_after_hours_service_fee(request) == Decimal("125.00")


def test_saturday_uses_flat_weekend_fee():
    request = ServiceRequest(appointment_start=dt(4, 14), appointment_end=dt(4, 15))
    assert calculate_after_hours_service_fee(request) == Decimal("275.00")


def test_holiday_overrides_weekday_business_hours():
    calendar = FacilityCalendar(holiday_dates=frozenset({date(2026, 7, 6)}))
    request = ServiceRequest(appointment_start=dt(6, 10), appointment_end=dt(6, 11))
    assert calculate_after_hours_service_fee(request, calendar) == Decimal("350.00")


def test_refrigerated_load_adds_premium_to_base_fee():
    request = ServiceRequest(appointment_start=dt(6, 19, 30), appointment_end=dt(6, 20), refrigerated=True)
    assert calculate_after_hours_service_fee(request) == Decimal("270.00")


def test_small_site_short_appointment_is_waived_even_if_refrigerated():
    calendar = FacilityCalendar(staff_count=4)
    request = ServiceRequest(appointment_start=dt(6, 19), appointment_end=dt(6, 19, 30), refrigerated=True)
    assert calculate_after_hours_service_fee(request, calendar) == Decimal("0.00")


def test_end_before_start_is_rejected():
    request = ServiceRequest(appointment_start=dt(6, 10), appointment_end=dt(6, 9, 59))
    with pytest.raises(ValueError):
        calculate_after_hours_service_fee(request)
