from datetime import date
from decimal import Decimal

import pytest

from weekend_service_fee import FeeSchedule, WeekendServiceRequest, calculate_weekend_service_fee


def d(day):
    return date(2026, 3, day)


def test_economy_load_never_pays_weekend_fee():
    request = WeekendServiceRequest(pickup_date=d(7), delivery_date=d(8), commitment="economy")
    assert calculate_weekend_service_fee(request) == Decimal("0.00")


def test_standard_load_pays_for_sunday_delivery_only():
    request = WeekendServiceRequest(pickup_date=d(6), delivery_date=d(8), commitment="standard")
    assert calculate_weekend_service_fee(request) == Decimal("75.00")


def test_standard_load_does_not_pay_for_saturday_pickup():
    request = WeekendServiceRequest(pickup_date=d(7), delivery_date=d(9), commitment="standard")
    assert calculate_weekend_service_fee(request) == Decimal("0.00")


def test_expedited_same_saturday_uses_bundle_fee():
    request = WeekendServiceRequest(pickup_date=d(7), delivery_date=d(7), commitment="expedited")
    assert calculate_weekend_service_fee(request) == Decimal("70.00")


def test_expedited_mixed_weekend_days_adds_separate_fees():
    request = WeekendServiceRequest(pickup_date=d(7), delivery_date=d(8), commitment="expedited")
    assert calculate_weekend_service_fee(request) == Decimal("110.00")


def test_lane_schedule_overrides_default_rates():
    lane = FeeSchedule(sunday_delivery=Decimal("82.25"))
    request = WeekendServiceRequest(
        pickup_date=d(6), delivery_date=d(8), commitment="standard", lane_schedule=lane
    )
    assert calculate_weekend_service_fee(request) == Decimal("82.25")


def test_customer_schedule_overrides_lane_schedule():
    lane = FeeSchedule(sunday_delivery=Decimal("82.25"))
    customer = FeeSchedule(sunday_delivery=Decimal("91.10"))
    request = WeekendServiceRequest(
        pickup_date=d(6),
        delivery_date=d(8),
        commitment="standard",
        lane_schedule=lane,
        customer_schedule=customer,
    )
    assert calculate_weekend_service_fee(request) == Decimal("91.10")


def test_missing_bundle_falls_back_to_separate_stop_fees():
    customer = FeeSchedule(sunday_pickup=Decimal("100.00"), sunday_delivery=Decimal("140.00"), sunday_both=None)
    request = WeekendServiceRequest(
        pickup_date=d(8), delivery_date=d(8), commitment="guaranteed", customer_schedule=customer
    )
    assert calculate_weekend_service_fee(request) == Decimal("240.00")


def test_fee_is_capped_per_load():
    customer = FeeSchedule(sunday_pickup=Decimal("150.00"), sunday_delivery=Decimal("140.00"), sunday_both=None)
    request = WeekendServiceRequest(
        pickup_date=d(8), delivery_date=d(8), commitment="guaranteed", customer_schedule=customer
    )
    assert calculate_weekend_service_fee(request) == Decimal("250.00")


def test_delivery_before_pickup_is_rejected():
    with pytest.raises(ValueError):
        calculate_weekend_service_fee(
            WeekendServiceRequest(pickup_date=d(9), delivery_date=d(8), commitment="expedited")
        )
