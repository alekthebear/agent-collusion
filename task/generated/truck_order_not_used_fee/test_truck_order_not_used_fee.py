from datetime import datetime
from decimal import Decimal

import pytest

from truck_order_not_used_fee import (
    TonuTerms,
    TruckOrderEvent,
    calculate_truck_order_not_used_fee,
)


def at(hour, minute=0):
    return datetime(2026, 5, 1, hour, minute)


def test_loaded_truck_has_no_tonu():
    event = TruckOrderEvent(
        appointment=at(10),
        canceled_at=at(9),
        dispatch_sent_at=at(8),
        loaded=True,
    )
    assert calculate_truck_order_not_used_fee(event) == Decimal("0.00")


def test_no_truck_assigned_is_free():
    event = TruckOrderEvent(
        appointment=at(10),
        canceled_at=at(9),
        truck_assigned=False,
    )
    assert calculate_truck_order_not_used_fee(event) == Decimal("0.00")


def test_dispatched_only_uses_35_percent_when_more_than_two_hours_out():
    event = TruckOrderEvent(
        appointment=at(12),
        canceled_at=at(9),
        dispatch_sent_at=at(8),
    )
    assert calculate_truck_order_not_used_fee(event) == Decimal("87.50")


def test_driver_assigned_respects_minimum_tonu():
    terms = TonuTerms(full_tonu=Decimal("100.00"), minimum_tonu=Decimal("75.00"))
    event = TruckOrderEvent(
        appointment=at(12),
        canceled_at=at(9),
        driver_assigned_at=at(8, 30),
    )
    assert calculate_truck_order_not_used_fee(event, terms) == Decimal("75.00")


def test_less_than_two_hours_before_appointment_bumps_to_90_percent():
    event = TruckOrderEvent(
        appointment=at(10),
        canceled_at=at(8, 30),
        dispatch_sent_at=at(7),
    )
    assert calculate_truck_order_not_used_fee(event) == Decimal("225.00")


def test_cancellation_at_appointment_is_full_tonu():
    event = TruckOrderEvent(
        appointment=at(10),
        canceled_at=at(10),
        driver_assigned_at=at(8),
    )
    assert calculate_truck_order_not_used_fee(event) == Decimal("250.00")


def test_arrival_at_shipper_bills_full_plus_deadhead_when_stackable():
    event = TruckOrderEvent(
        appointment=at(10),
        canceled_at=at(9, 45),
        dispatch_sent_at=at(7),
        driver_assigned_at=at(7, 30),
        en_route_at=at(8),
        arrived_at_shipper_at=at(9, 40),
        deadhead_miles=Decimal("12.2"),
    )
    assert calculate_truck_order_not_used_fee(event) == Decimal("277.30")


def test_non_stackable_uses_larger_of_tonu_and_deadhead():
    terms = TonuTerms(stack_deadhead_with_tonu=False)
    event = TruckOrderEvent(
        appointment=at(12),
        canceled_at=at(9),
        dispatch_sent_at=at(8),
        deadhead_miles=Decimal("200.1"),
    )
    assert calculate_truck_order_not_used_fee(event, terms) == Decimal("422.10")


def test_deadhead_miles_round_up_to_next_whole_mile():
    terms = TonuTerms(full_tonu=Decimal("0.00"), minimum_tonu=Decimal("0.00"))
    event = TruckOrderEvent(
        appointment=at(12),
        canceled_at=at(9),
        dispatch_sent_at=at(8),
        deadhead_miles=Decimal("10.01"),
    )
    assert calculate_truck_order_not_used_fee(event, terms) == Decimal("23.10")


def test_milestone_after_cancellation_is_rejected():
    event = TruckOrderEvent(
        appointment=at(10),
        canceled_at=at(9),
        dispatch_sent_at=at(9, 1),
    )
    with pytest.raises(ValueError):
        calculate_truck_order_not_used_fee(event)
