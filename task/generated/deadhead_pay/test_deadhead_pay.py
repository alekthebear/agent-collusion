from decimal import Decimal

import pytest

from deadhead_pay import DeadheadMove, DeadheadTerms, calculate_deadhead_pay


def test_miles_within_free_threshold_do_not_pay():
    move = DeadheadMove(approved_miles=Decimal("25.9"))
    assert calculate_deadhead_pay(move) == Decimal("0.00")


def test_fractional_miles_are_rounded_down_before_free_miles():
    move = DeadheadMove(approved_miles=Decimal("25.99"))
    assert calculate_deadhead_pay(move) == Decimal("0.00")


def test_mileage_pay_applies_below_flat_threshold():
    move = DeadheadMove(approved_miles=Decimal("60.0"))
    assert calculate_deadhead_pay(move) == Decimal("38.50")


def test_flat_threshold_uses_greater_of_mileage_or_flat_amount():
    move = DeadheadMove(approved_miles=Decimal("105.0"))
    assert calculate_deadhead_pay(move) == Decimal("88.00")


def test_flat_amount_wins_when_threshold_met_but_mileage_is_lower():
    terms = DeadheadTerms(mile_rate=Decimal("0.80"))
    move = DeadheadMove(approved_miles=Decimal("105.0"))
    assert calculate_deadhead_pay(move, terms) == Decimal("75.00")


def test_same_market_adds_extra_free_miles():
    move = DeadheadMove(approved_miles=Decimal("40.0"), same_market=True)
    assert calculate_deadhead_pay(move) == Decimal("5.50")


def test_canceled_short_move_under_five_miles_never_pays():
    move = DeadheadMove(approved_miles=Decimal("4.9"), canceled=True)
    assert calculate_deadhead_pay(move) == Decimal("0.00")


def test_canceled_move_also_gets_extra_free_miles():
    move = DeadheadMove(approved_miles=Decimal("50.0"), canceled=True)
    assert calculate_deadhead_pay(move) == Decimal("11.00")


def test_event_cap_limits_large_payout_and_none_removes_cap():
    move = DeadheadMove(approved_miles=Decimal("400.0"))
    assert calculate_deadhead_pay(move) == Decimal("250.00")
    uncapped = DeadheadTerms(event_cap=None)
    assert calculate_deadhead_pay(move, uncapped) == Decimal("412.50")


def test_negative_miles_are_rejected():
    with pytest.raises(ValueError):
        calculate_deadhead_pay(DeadheadMove(approved_miles=Decimal("-1.0")))
