from datetime import datetime
from decimal import Decimal

import pytest

from chassis_split_fee import SplitMove, SplitTerms, calculate_chassis_split_fee


def at(day, hour, minute=0):
    return datetime(2026, 4, day, hour, minute)


def test_base_fee_applies_when_round_trip_is_within_included_miles():
    move = SplitMove(terminal_to_yard_miles=Decimal("2.5"), completed_at=at(6, 10))
    assert calculate_chassis_split_fee(move) == Decimal("95.00")


def test_extra_miles_bill_round_trip_beyond_included_threshold():
    move = SplitMove(terminal_to_yard_miles=Decimal("4"), completed_at=at(6, 10))
    assert calculate_chassis_split_fee(move) == Decimal("107.75")


def test_exact_included_miles_boundary_has_no_mileage_charge():
    move = SplitMove(terminal_to_yard_miles=Decimal("2.5"), completed_at=at(7, 0))
    assert calculate_chassis_split_fee(move) == Decimal("130.00")


def test_dual_transaction_credit_reduces_charge():
    move = SplitMove(
        terminal_to_yard_miles=Decimal("4"), completed_at=at(6, 10), dual_transaction=True
    )
    assert calculate_chassis_split_fee(move) == Decimal("82.75")


def test_after_hours_surcharge_applies_at_1800_boundary():
    move = SplitMove(terminal_to_yard_miles=Decimal("4"), completed_at=at(6, 18, 0))
    assert calculate_chassis_split_fee(move) == Decimal("142.75")


def test_weekend_is_after_hours_even_in_daytime():
    move = SplitMove(terminal_to_yard_miles=Decimal("3"), completed_at=at(11, 12, 0))
    assert calculate_chassis_split_fee(move) == Decimal("134.25")


def test_customer_contract_can_override_flat_fee_and_mileage_rate():
    move = SplitMove(
        terminal_to_yard_miles=Decimal("6"),
        completed_at=at(7, 9, 0),
        customer_flat_fee=Decimal("120.00"),
        customer_mileage_rate=Decimal("3.50"),
    )
    assert calculate_chassis_split_fee(move) == Decimal("144.50")


def test_waived_mileage_ignores_extra_miles():
    move = SplitMove(
        terminal_to_yard_miles=Decimal("10"), completed_at=at(8, 11, 0), waive_mileage=True
    )
    assert calculate_chassis_split_fee(move) == Decimal("95.00")


def test_minimum_billable_floor_applies_after_credit():
    terms = SplitTerms(minimum_billable=Decimal("70.00"))
    move = SplitMove(
        terminal_to_yard_miles=Decimal("0"),
        completed_at=at(8, 11, 0),
        dual_transaction=True,
    )
    assert calculate_chassis_split_fee(move, terms) == Decimal("70.00")


def test_negative_miles_are_rejected():
    with pytest.raises(ValueError):
        calculate_chassis_split_fee(
            SplitMove(terminal_to_yard_miles=Decimal("-1"), completed_at=at(6, 10))
        )
