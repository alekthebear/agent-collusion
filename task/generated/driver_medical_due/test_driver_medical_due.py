from datetime import date, timedelta

import pytest

from driver_medical_due import DriverMedicalRecord, calculate_driver_medical_due


def day(n):
    return date(2026, 4, 1) + timedelta(days=n)


def test_standard_driver_becomes_due_soon_at_30_days():
    record = DriverMedicalRecord(expiration_date=day(30), review_date=day(0))
    result = calculate_driver_medical_due(record)
    assert result.status == "due_soon"
    assert result.due_soon_threshold_days == 30
    assert result.dispatch_eligible is True
    assert result.next_review_date == day(0)


def test_standard_driver_is_current_at_31_days():
    record = DriverMedicalRecord(expiration_date=day(31), review_date=day(0))
    result = calculate_driver_medical_due(record)
    assert result.status == "current"
    assert result.dispatch_eligible is True
    assert result.next_review_date == day(1)


def test_hazmat_driver_uses_21_day_threshold():
    record = DriverMedicalRecord(expiration_date=day(22), review_date=day(0), hazmat_qualified=True)
    result = calculate_driver_medical_due(record)
    assert result.status == "current"
    assert result.due_soon_threshold_days == 21
    assert result.next_review_date == day(1)


def test_medical_variance_reduces_due_soon_threshold():
    record = DriverMedicalRecord(expiration_date=day(15), review_date=day(0), medical_variance=True)
    result = calculate_driver_medical_due(record)
    assert result.status == "due_soon"
    assert result.due_soon_threshold_days == 20
    assert result.next_review_date == day(-5)


def test_variance_threshold_never_drops_below_minimum():
    record = DriverMedicalRecord(
        expiration_date=day(8),
        review_date=day(0),
        hazmat_qualified=True,
        medical_variance=True,
    )
    result = calculate_driver_medical_due(record)
    assert result.due_soon_threshold_days == 11
    assert result.status == "due_soon"


def test_expired_within_grace_is_not_dispatch_eligible():
    record = DriverMedicalRecord(expiration_date=day(-3), review_date=day(0))
    result = calculate_driver_medical_due(record)
    assert result.status == "grace"
    assert result.dispatch_eligible is False
    assert result.grace_end_date == day(12)
    assert result.next_review_date == day(0)


def test_expired_past_grace_is_fully_expired():
    record = DriverMedicalRecord(expiration_date=day(-16), review_date=day(0))
    result = calculate_driver_medical_due(record)
    assert result.status == "expired"
    assert result.dispatch_eligible is False
    assert result.grace_end_date is None


def test_long_haul_requires_extra_two_day_buffer():
    record = DriverMedicalRecord(expiration_date=day(8), review_date=day(0), dispatch_horizon_days=8)
    result = calculate_driver_medical_due(record)
    assert result.status == "due_soon"
    assert result.dispatch_eligible is False


def test_horizon_of_seven_days_does_not_add_buffer():
    record = DriverMedicalRecord(expiration_date=day(7), review_date=day(0), dispatch_horizon_days=7)
    result = calculate_driver_medical_due(record)
    assert result.dispatch_eligible is True


def test_negative_dispatch_horizon_is_rejected():
    with pytest.raises(ValueError):
        calculate_driver_medical_due(
            DriverMedicalRecord(expiration_date=day(20), review_date=day(0), dispatch_horizon_days=-1)
        )
