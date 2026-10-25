from datetime import datetime
from decimal import Decimal

import pytest

from service_failure_penalty import (
    PenaltyTerms,
    ServiceFailure,
    calculate_service_failure_penalty,
)


def at(hour, minute=0):
    return datetime(2026, 4, 7, hour, minute)


def test_late_pickup_within_grace_is_free():
    failure = ServiceFailure("late_pickup", appointment=at(8), event_time=at(8, 15))
    assert calculate_service_failure_penalty(failure) == Decimal("0.00")


def test_late_pickup_partial_block_bills_started_block():
    failure = ServiceFailure("late_pickup", appointment=at(8), event_time=at(8, 16))
    assert calculate_service_failure_penalty(failure) == Decimal("185.00")


def test_late_delivery_uses_its_own_base_and_rate():
    failure = ServiceFailure("late_delivery", appointment=at(9), event_time=at(10, 20))
    assert calculate_service_failure_penalty(failure) == Decimal("350.00")


def test_missed_appointment_rescheduled_same_day_is_waived():
    failure = ServiceFailure(
        "missed_appointment",
        appointment=at(11),
        event_time=at(13),
        rescheduled_same_day=True,
    )
    assert calculate_service_failure_penalty(failure) == Decimal("0.00")


def test_missed_appointment_without_reschedule_bills_flat_fee():
    failure = ServiceFailure("missed_appointment", appointment=at(11), event_time=at(13))
    assert calculate_service_failure_penalty(failure) == Decimal("250.00")


def test_tonu_with_two_hours_notice_gets_reduced_fee():
    failure = ServiceFailure("truck_order_not_used", appointment=at(14), event_time=at(12))
    assert calculate_service_failure_penalty(failure) == Decimal("125.00")


def test_tonu_with_less_than_two_hours_notice_gets_full_fee():
    failure = ServiceFailure("truck_order_not_used", appointment=at(14), event_time=at(12, 1))
    assert calculate_service_failure_penalty(failure) == Decimal("250.00")


def test_tonu_after_appointment_does_not_bill():
    failure = ServiceFailure("truck_order_not_used", appointment=at(14), event_time=at(14, 5))
    assert calculate_service_failure_penalty(failure) == Decimal("0.00")


def test_customer_fault_waives_otherwise_billable_penalty():
    failure = ServiceFailure(
        "late_delivery",
        appointment=at(9),
        event_time=at(11),
        customer_at_fault=True,
    )
    assert calculate_service_failure_penalty(failure) == Decimal("0.00")


def test_cap_limits_large_late_delivery_penalty():
    failure = ServiceFailure("late_delivery", appointment=at(8), event_time=at(12))
    assert calculate_service_failure_penalty(failure) == Decimal("500.00")
    uncapped = PenaltyTerms(cap=None)
    assert calculate_service_failure_penalty(failure, uncapped) == Decimal("600.00")
