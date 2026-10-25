from datetime import datetime
from decimal import Decimal

import pytest

from reconsignment_fee import (
    ReconsignmentRequest,
    ReconsignmentTerms,
    calculate_reconsignment_fee,
)


def at(hour, minute=0):
    return datetime(2026, 4, 7, hour, minute)


def test_instruction_before_dispatch_is_free():
    request = ReconsignmentRequest(
        dispatched_at=at(8),
        instructed_at=at(7, 45),
        arrived_first_affected_stop_at=None,
        miles_already_traveled=Decimal("20"),
        original_stop_count=1,
        new_stop_count=2,
    )
    assert calculate_reconsignment_fee(request) == Decimal("0.00")


def test_same_location_clerical_correction_is_free_after_dispatch():
    request = ReconsignmentRequest(
        dispatched_at=at(8),
        instructed_at=at(8, 5),
        arrived_first_affected_stop_at=None,
        miles_already_traveled=Decimal("0"),
        original_stop_count=2,
        new_stop_count=2,
        same_city_change=True,
    )
    assert calculate_reconsignment_fee(request) == Decimal("0.00")


def test_tariff_base_fee_only_within_free_miles():
    request = ReconsignmentRequest(
        dispatched_at=at(8),
        instructed_at=at(9),
        arrived_first_affected_stop_at=None,
        miles_already_traveled=Decimal("15"),
        original_stop_count=1,
        new_stop_count=1,
    )
    assert calculate_reconsignment_fee(request) == Decimal("85.00")


def test_tariff_mileage_applies_past_free_miles_and_rounds_half_up():
    request = ReconsignmentRequest(
        dispatched_at=at(8),
        instructed_at=at(9),
        arrived_first_affected_stop_at=None,
        miles_already_traveled=Decimal("15.005"),
        original_stop_count=1,
        new_stop_count=1,
    )
    assert calculate_reconsignment_fee(request) == Decimal("85.01")


def test_same_city_tariff_change_owes_base_but_no_mileage():
    request = ReconsignmentRequest(
        dispatched_at=at(8),
        instructed_at=at(9),
        arrived_first_affected_stop_at=None,
        miles_already_traveled=Decimal("80"),
        original_stop_count=1,
        new_stop_count=1,
        same_city_change=True,
    )
    assert calculate_reconsignment_fee(request) == Decimal("85.00")


def test_contract_same_city_prearrival_uses_clerical_fee():
    request = ReconsignmentRequest(
        dispatched_at=at(8),
        instructed_at=at(9),
        arrived_first_affected_stop_at=at(10),
        miles_already_traveled=Decimal("4"),
        original_stop_count=1,
        new_stop_count=1,
        same_city_change=True,
        contract_flat_fee=True,
    )
    assert calculate_reconsignment_fee(request) == Decimal("35.00")


def test_after_arrival_surcharge_applies_on_instruction_at_arrival_time():
    request = ReconsignmentRequest(
        dispatched_at=at(8),
        instructed_at=at(10),
        arrived_first_affected_stop_at=at(10),
        miles_already_traveled=Decimal("0"),
        original_stop_count=1,
        new_stop_count=1,
        contract_flat_fee=True,
    )
    assert calculate_reconsignment_fee(request) == Decimal("185.00")


def test_added_stop_fee_bills_only_up_to_cap_of_two_added_stops():
    request = ReconsignmentRequest(
        dispatched_at=at(8),
        instructed_at=at(9),
        arrived_first_affected_stop_at=None,
        miles_already_traveled=Decimal("15"),
        original_stop_count=1,
        new_stop_count=4,
    )
    assert calculate_reconsignment_fee(request) == Decimal("165.00")


def test_total_fee_is_capped():
    request = ReconsignmentRequest(
        dispatched_at=at(8),
        instructed_at=at(11),
        arrived_first_affected_stop_at=at(10),
        miles_already_traveled=Decimal("200"),
        original_stop_count=1,
        new_stop_count=4,
    )
    assert calculate_reconsignment_fee(request) == Decimal("425.00")


def test_negative_miles_are_rejected():
    request = ReconsignmentRequest(
        dispatched_at=at(8),
        instructed_at=at(9),
        arrived_first_affected_stop_at=None,
        miles_already_traveled=Decimal("-1"),
        original_stop_count=1,
        new_stop_count=1,
    )
    with pytest.raises(ValueError):
        calculate_reconsignment_fee(request)
