from datetime import date
from decimal import Decimal

import pytest

from credit_hold_check import AgingBalances, CreditAccount, evaluate_credit_hold_check


def d(day):
    return date(2026, 4, day)


def test_small_balance_is_not_held():
    aging = AgingBalances(current=Decimal("49.99"))
    account = CreditAccount(credit_limit=Decimal("1000.00"), opened_on=d(1), as_of=d(30))
    assert evaluate_credit_hold_check(aging, account) is False


def test_cash_only_customer_is_always_held():
    aging = AgingBalances(current=Decimal("0.00"))
    account = CreditAccount(credit_limit=Decimal("500.00"), opened_on=d(1), as_of=d(2), cash_only=True)
    assert evaluate_credit_hold_check(aging, account) is True


def test_returned_payment_holds_when_exposure_remains():
    aging = AgingBalances(current=Decimal("10.00"), due_1_30=Decimal("40.00"))
    account = CreditAccount(
        credit_limit=Decimal("1000.00"), opened_on=d(1), as_of=d(30), returned_payment=True
    )
    assert evaluate_credit_hold_check(aging, account) is True


def test_returned_payment_with_zero_effective_exposure_is_not_held():
    aging = AgingBalances(current=Decimal("100.00"), disputed_total=Decimal("100.00"))
    account = CreditAccount(
        credit_limit=Decimal("1000.00"), opened_on=d(1), as_of=d(30), returned_payment=True
    )
    assert evaluate_credit_hold_check(aging, account) is False


def test_over_90_non_disputed_balance_triggers_hold():
    aging = AgingBalances(over_90=Decimal("250.00"))
    account = CreditAccount(credit_limit=Decimal("1000.00"), opened_on=d(1), as_of=d(30))
    assert evaluate_credit_hold_check(aging, account) is True


def test_grace_window_suppresses_over_90_hold():
    aging = AgingBalances(over_90=Decimal("300.00"), current=Decimal("100.00"))
    account = CreditAccount(
        credit_limit=Decimal("1000.00"),
        opened_on=d(1),
        as_of=d(30),
        recent_payment_amount=Decimal("80.00"),
        recent_payment_date=d(28),
    )
    assert evaluate_credit_hold_check(aging, account) is False


def test_disputes_reduce_exposure_before_limit_check():
    aging = AgingBalances(current=Decimal("700.00"), due_1_30=Decimal("400.00"), disputed_total=Decimal("150.00"))
    account = CreditAccount(credit_limit=Decimal("1000.00"), opened_on=d(1), as_of=d(30))
    assert evaluate_credit_hold_check(aging, account) is False


def test_autopay_gets_extra_limit_cushion_but_boundary_holds():
    aging = AgingBalances(current=Decimal("1050.00"))
    account = CreditAccount(
        credit_limit=Decimal("1000.00"), opened_on=d(1), as_of=d(30), autopay_enrolled=True
    )
    assert evaluate_credit_hold_check(aging, account) is True


def test_new_account_not_held_for_limit_usage_alone():
    aging = AgingBalances(current=Decimal("1200.00"))
    account = CreditAccount(credit_limit=Decimal("1000.00"), opened_on=d(20), as_of=d(30))
    assert evaluate_credit_hold_check(aging, account) is False


def test_negative_amounts_are_rejected():
    aging = AgingBalances(current=Decimal("-1.00"))
    account = CreditAccount(credit_limit=Decimal("1000.00"), opened_on=d(1), as_of=d(30))
    with pytest.raises(ValueError):
        evaluate_credit_hold_check(aging, account)
