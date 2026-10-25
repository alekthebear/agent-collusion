from decimal import Decimal

import pytest

from trailer_pool_balance import PoolEvent, PoolTerms, calculate_trailer_pool_balance


def test_exact_target_has_no_charge_or_credit():
    terms = PoolTerms(target_level=10)
    result = calculate_trailer_pool_balance(8, [PoolEvent("inbound", 2)], terms)
    assert result.ending_inventory == 10
    assert result.variance_to_target == 0
    assert result.net_balance == Decimal("0.00")


def test_shortage_below_deadband_is_ignored():
    terms = PoolTerms(target_level=10, deadband=1)
    result = calculate_trailer_pool_balance(9, [], terms)
    assert result.variance_to_target == 0
    assert result.shortage_trailers == 0
    assert result.charge == Decimal("0.00")


def test_shortage_outside_deadband_is_charged_per_trailer():
    terms = PoolTerms(target_level=10, shortage_rate=Decimal("18.50"), deadband=1)
    result = calculate_trailer_pool_balance(7, [], terms)
    assert result.variance_to_target == -3
    assert result.shortage_trailers == 3
    assert result.charge == Decimal("55.50")
    assert result.net_balance == Decimal("55.50")


def test_small_surplus_is_free_until_allowance_exceeded():
    terms = PoolTerms(target_level=10, deadband=0, free_surplus=2, surplus_rate=Decimal("4.25"))
    result = calculate_trailer_pool_balance(12, [], terms)
    assert result.variance_to_target == 2
    assert result.surplus_trailers == 0
    assert result.credit == Decimal("0.00")


def test_surplus_above_allowance_credits_only_excess_units():
    terms = PoolTerms(target_level=10, deadband=0, free_surplus=2, surplus_rate=Decimal("4.25"))
    result = calculate_trailer_pool_balance(15, [], terms)
    assert result.variance_to_target == 5
    assert result.surplus_trailers == 3
    assert result.credit == Decimal("12.75")
    assert result.net_balance == Decimal("-12.75")


def test_yard_check_can_reduce_inventory():
    terms = PoolTerms(target_level=10, deadband=0)
    events = [PoolEvent("inbound", 4), PoolEvent("yard_check", -2)]
    result = calculate_trailer_pool_balance(8, events, terms)
    assert result.ending_inventory == 10
    assert result.net_balance == Decimal("0.00")


def test_inventory_is_floored_at_zero_before_balance():
    terms = PoolTerms(target_level=4, deadband=0)
    result = calculate_trailer_pool_balance(3, [PoolEvent("outbound", 10)], terms)
    assert result.ending_inventory == 0
    assert result.variance_to_target == -4
    assert result.charge == Decimal("74.00")


def test_negative_starting_inventory_is_rejected():
    terms = PoolTerms(target_level=5)
    with pytest.raises(ValueError):
        calculate_trailer_pool_balance(-1, [], terms)


def test_unknown_event_kind_is_rejected():
    terms = PoolTerms(target_level=5)
    with pytest.raises(ValueError):
        calculate_trailer_pool_balance(5, [PoolEvent("transfer", 1)], terms)


def test_non_yard_check_negative_quantity_is_rejected():
    terms = PoolTerms(target_level=5)
    with pytest.raises(ValueError):
        calculate_trailer_pool_balance(5, [PoolEvent("inbound", -1)], terms)
