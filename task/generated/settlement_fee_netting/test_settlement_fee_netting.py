from decimal import Decimal

import pytest

from settlement_fee_netting import (
    PayableBalance,
    ReceivableBalance,
    calculate_settlement_fee_netting,
)


def test_basic_same_entity_netting_reduces_payable():
    payable = PayableBalance(entity_code="TWG", amount=Decimal("1000.00"), days_old=10)
    receivables = [
        ReceivableBalance(entity_code="TWG", amount=Decimal("250.00"), days_past_due=30),
        ReceivableBalance(entity_code="TWG", amount=Decimal("100.00"), days_past_due=0),
    ]
    result = calculate_settlement_fee_netting(payable, receivables)
    assert result.netted_amount == Decimal("350.00")
    assert result.expedite_fee == Decimal("0.00")
    assert result.net_payable == Decimal("650.00")


def test_different_entity_receivables_do_not_offset():
    payable = PayableBalance(entity_code="TWTX", amount=Decimal("400.00"), days_old=5)
    receivables = [ReceivableBalance(entity_code="TWCA", amount=Decimal("300.00"), days_past_due=20)]
    result = calculate_settlement_fee_netting(payable, receivables)
    assert result.netted_amount == Decimal("0.00")
    assert result.net_payable == Decimal("400.00")


def test_receivable_must_be_within_aging_window_inclusive():
    payable = PayableBalance(entity_code="TWG", amount=Decimal("500.00"), days_old=1)
    receivables = [
        ReceivableBalance(entity_code="TWG", amount=Decimal("100.00"), days_past_due=120),
        ReceivableBalance(entity_code="TWG", amount=Decimal("50.00"), days_past_due=121),
    ]
    result = calculate_settlement_fee_netting(payable, receivables)
    assert result.netted_amount == Decimal("100.00")
    assert result.net_payable == Decimal("400.00")


def test_credit_hold_receivable_nets_at_half_value():
    payable = PayableBalance(entity_code="TWG", amount=Decimal("500.00"), days_old=2)
    receivables = [ReceivableBalance(entity_code="TWG", amount=Decimal("80.00"), days_past_due=10, credit_hold=True)]
    result = calculate_settlement_fee_netting(payable, receivables)
    assert result.netted_amount == Decimal("40.00")
    assert result.net_payable == Decimal("460.00")


def test_small_receivable_under_threshold_is_ignored():
    payable = PayableBalance(entity_code="TWG", amount=Decimal("60.00"), days_old=2)
    receivables = [ReceivableBalance(entity_code="TWG", amount=Decimal("4.99"), days_past_due=5)]
    result = calculate_settlement_fee_netting(payable, receivables)
    assert result.netted_amount == Decimal("0.00")
    assert result.net_payable == Decimal("60.00")


def test_payable_must_be_ready_and_not_too_old():
    payable = PayableBalance(entity_code="TWG", amount=Decimal("200.00"), days_old=46, ready_to_pay=True)
    receivables = [ReceivableBalance(entity_code="TWG", amount=Decimal("50.00"), days_past_due=10)]
    result = calculate_settlement_fee_netting(payable, receivables)
    assert result.netted_amount == Decimal("0.00")
    assert result.expedite_fee == Decimal("0.00")
    assert result.net_payable == Decimal("200.00")


def test_netted_amount_cannot_exceed_payable_and_expedite_fee_has_minimum():
    payable = PayableBalance(entity_code="TWG", amount=Decimal("100.00"), days_old=4, expedite_requested=True)
    receivables = [ReceivableBalance(entity_code="TWG", amount=Decimal("300.00"), days_past_due=15)]
    result = calculate_settlement_fee_netting(payable, receivables)
    assert result.netted_amount == Decimal("100.00")
    assert result.expedite_fee == Decimal("2.00")
    assert result.net_payable == Decimal("2.00")


def test_expedite_fee_is_capped_at_maximum():
    payable = PayableBalance(entity_code="TWG", amount=Decimal("5000.00"), days_old=3, expedite_requested=True)
    receivables = [ReceivableBalance(entity_code="TWG", amount=Decimal("3000.00"), days_past_due=12)]
    result = calculate_settlement_fee_netting(payable, receivables)
    assert result.netted_amount == Decimal("3000.00")
    assert result.expedite_fee == Decimal("25.00")
    assert result.net_payable == Decimal("2025.00")


def test_disputed_or_unapproved_receivables_are_not_eligible():
    payable = PayableBalance(entity_code="TWG", amount=Decimal("300.00"), days_old=8)
    receivables = [
        ReceivableBalance(entity_code="TWG", amount=Decimal("100.00"), days_past_due=10, disputed=True),
        ReceivableBalance(entity_code="TWG", amount=Decimal("75.00"), days_past_due=10, approved=False),
        ReceivableBalance(entity_code="TWG", amount=Decimal("25.00"), days_past_due=10),
    ]
    result = calculate_settlement_fee_netting(payable, receivables)
    assert result.netted_amount == Decimal("25.00")
    assert result.net_payable == Decimal("275.00")


def test_negative_amounts_are_rejected():
    payable = PayableBalance(entity_code="TWG", amount=Decimal("100.00"), days_old=1)
    with pytest.raises(ValueError):
        calculate_settlement_fee_netting(
            payable,
            [ReceivableBalance(entity_code="TWG", amount=Decimal("-1.00"), days_past_due=1)],
        )
    with pytest.raises(ValueError):
        calculate_settlement_fee_netting(
            PayableBalance(entity_code="TWG", amount=Decimal("-1.00"), days_old=1),
            [],
        )
