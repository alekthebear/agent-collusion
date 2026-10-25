from decimal import Decimal

import pytest

from inside_delivery_fee import (
    InsideDeliveryRequest,
    InsideDeliveryTerms,
    calculate_inside_delivery_fee,
)


def test_threshold_base_is_raised_to_minimum_charge():
    request = InsideDeliveryRequest(
        service_level="threshold",
        floor_count=1,
        has_elevator=False,
        piece_count=1,
    )
    assert calculate_inside_delivery_fee(request) == Decimal("55.00")


def test_room_of_choice_uses_base_when_above_minimum():
    request = InsideDeliveryRequest(
        service_level="room_of_choice",
        floor_count=1,
        has_elevator=False,
        piece_count=4,
    )
    assert calculate_inside_delivery_fee(request) == Decimal("85.00")


def test_one_floor_is_included_and_ground_floor_has_no_surcharge():
    floor_one = InsideDeliveryRequest("room_of_choice", 1, False, 1)
    ground = InsideDeliveryRequest("room_of_choice", 0, False, 1)
    assert calculate_inside_delivery_fee(floor_one) == Decimal("85.00")
    assert calculate_inside_delivery_fee(ground) == Decimal("85.00")


def test_extra_floors_without_elevator_bill_full_rate():
    request = InsideDeliveryRequest(
        service_level="room_of_choice",
        floor_count=3,
        has_elevator=False,
        piece_count=2,
    )
    assert calculate_inside_delivery_fee(request) == Decimal("135.00")


def test_extra_floors_with_elevator_bill_reduced_rate():
    request = InsideDeliveryRequest(
        service_level="room_of_choice",
        floor_count=3,
        has_elevator=True,
        piece_count=2,
    )
    assert calculate_inside_delivery_fee(request) == Decimal("113.00")


def test_piece_surcharge_starts_after_included_count():
    included = InsideDeliveryRequest("room_of_choice", 1, False, 10)
    over = InsideDeliveryRequest("room_of_choice", 1, False, 12)
    assert calculate_inside_delivery_fee(included) == Decimal("85.00")
    assert calculate_inside_delivery_fee(over) == Decimal("92.00")


def test_white_glove_includes_more_pieces_before_surcharge():
    request = InsideDeliveryRequest(
        service_level="white_glove",
        floor_count=2,
        has_elevator=True,
        piece_count=18,
    )
    assert calculate_inside_delivery_fee(request) == Decimal("170.50")


def test_threshold_large_piece_count_adds_heavy_handling_bump():
    request = InsideDeliveryRequest(
        service_level="threshold",
        floor_count=1,
        has_elevator=False,
        piece_count=25,
    )
    assert calculate_inside_delivery_fee(request) == Decimal("125.50")


def test_custom_minimum_can_raise_otherwise_computed_amount():
    request = InsideDeliveryRequest(
        service_level="room_of_choice",
        floor_count=1,
        has_elevator=False,
        piece_count=1,
    )
    terms = InsideDeliveryTerms(minimum_charge=Decimal("95.00"))
    assert calculate_inside_delivery_fee(request, terms) == Decimal("95.00")


def test_invalid_values_are_rejected():
    with pytest.raises(ValueError):
        calculate_inside_delivery_fee(
            InsideDeliveryRequest("premium", 1, False, 1)
        )
    with pytest.raises(ValueError):
        calculate_inside_delivery_fee(
            InsideDeliveryRequest("threshold", -1, False, 1)
        )
    with pytest.raises(ValueError):
        calculate_inside_delivery_fee(
            InsideDeliveryRequest("threshold", 1, False, -2)
        )
