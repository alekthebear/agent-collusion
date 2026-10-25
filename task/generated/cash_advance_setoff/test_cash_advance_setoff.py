from decimal import Decimal

import pytest

from cash_advance_setoff import (
    CashAdvanceStatus,
    SetoffTerms,
    SettlementAmounts,
    calculate_cash_advance_setoff,
)


def test_standard_repayment_uses_linehaul_only():
    amounts = SettlementAmounts(
        linehaul=Decimal("1000.00"),
        fuel_reimbursement=Decimal("200.00"),
        lumper_reimbursement=Decimal("50.00"),
        other_deductions=Decimal("100.00"),
    )
    status = CashAdvanceStatus(outstanding_balance=Decimal("800.00"))
    assert calculate_cash_advance_setoff(amounts, status) == Decimal("350.00")


def test_outstanding_below_collectible_minimum_is_not_set_off():
    amounts = SettlementAmounts(linehaul=Decimal("900.00"))
    status = CashAdvanceStatus(outstanding_balance=Decimal("24.99"))
    assert calculate_cash_advance_setoff(amounts, status) == Decimal("0.00")


def test_linehaul_below_threshold_blocks_setoff_even_with_reimbursements():
    amounts = SettlementAmounts(
        linehaul=Decimal("149.99"),
        fuel_reimbursement=Decimal("300.00"),
    )
    status = CashAdvanceStatus(outstanding_balance=Decimal("100.00"))
    assert calculate_cash_advance_setoff(amounts, status) == Decimal("0.00")


def test_minimum_net_pay_limits_setoff():
    amounts = SettlementAmounts(
        linehaul=Decimal("500.00"),
        other_deductions=Decimal("300.00"),
    )
    status = CashAdvanceStatus(outstanding_balance=Decimal("500.00"))
    assert calculate_cash_advance_setoff(amounts, status) == Decimal("100.00")


def test_other_deductions_can_reduce_payable_to_zero():
    amounts = SettlementAmounts(
        linehaul=Decimal("400.00"),
        fuel_reimbursement=Decimal("20.00"),
        other_deductions=Decimal("450.00"),
    )
    status = CashAdvanceStatus(outstanding_balance=Decimal("300.00"))
    assert calculate_cash_advance_setoff(amounts, status) == Decimal("0.00")


def test_setoff_cannot_exceed_outstanding_balance():
    amounts = SettlementAmounts(linehaul=Decimal("1000.00"))
    status = CashAdvanceStatus(outstanding_balance=Decimal("125.10"))
    assert calculate_cash_advance_setoff(amounts, status) == Decimal("125.10")


def test_threshold_values_are_inclusive_for_collection():
    amounts = SettlementAmounts(linehaul=Decimal("150.00"))
    status = CashAdvanceStatus(outstanding_balance=Decimal("25.00"))
    assert calculate_cash_advance_setoff(amounts, status) == Decimal("25.00")


def test_half_up_rounding_applies_to_percentage_calculation():
    amounts = SettlementAmounts(linehaul=Decimal("285.50"))
    status = CashAdvanceStatus(outstanding_balance=Decimal("500.00"))
    terms = SetoffTerms(repayment_rate=Decimal("0.333"))
    assert calculate_cash_advance_setoff(amounts, status, terms) == Decimal("95.07")


def test_negative_inputs_are_rejected():
    with pytest.raises(ValueError):
        calculate_cash_advance_setoff(
            SettlementAmounts(linehaul=Decimal("100.00"), other_deductions=Decimal("-1.00")),
            CashAdvanceStatus(outstanding_balance=Decimal("50.00")),
        )
