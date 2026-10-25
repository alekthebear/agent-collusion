from decimal import Decimal

import pytest

from factoring_fee_deduction import (
    FactoringTerms,
    ReceivableBreakdown,
    calculate_factoring_fee_deduction,
)


def test_linehaul_only_uses_base_fee_and_reserve():
    result = calculate_factoring_fee_deduction(ReceivableBreakdown(linehaul=Decimal("1000.00")))
    assert result.eligible_amount == Decimal("1000.00")
    assert result.fee_amount == Decimal("30.00")
    assert result.reserve_amount == Decimal("100.00")
    assert result.advance_amount == Decimal("870.00")


def test_fuel_is_excluded_when_not_assignable():
    receivable = ReceivableBreakdown(
        linehaul=Decimal("1000.00"),
        fuel_surcharge=Decimal("200.00"),
        fuel_assignable=False,
    )
    result = calculate_factoring_fee_deduction(receivable)
    assert result.eligible_amount == Decimal("1000.00")
    assert result.fee_amount == Decimal("30.00")


def test_accessorials_are_excluded_by_default():
    receivable = ReceivableBreakdown(
        linehaul=Decimal("1000.00"),
        accessorials=Decimal("150.00"),
    )
    result = calculate_factoring_fee_deduction(receivable)
    assert result.eligible_amount == Decimal("1000.00")
    assert result.advance_amount == Decimal("870.00")


def test_accessorials_can_be_included_when_marked_eligible():
    receivable = ReceivableBreakdown(
        linehaul=Decimal("1000.00"),
        accessorials=Decimal("150.00"),
        accessorials_eligible=True,
    )
    result = calculate_factoring_fee_deduction(receivable)
    assert result.eligible_amount == Decimal("1150.00")
    assert result.fee_amount == Decimal("34.50")
    assert result.reserve_amount == Decimal("115.00")
    assert result.advance_amount == Decimal("1000.50")


def test_same_day_submission_discount_reduces_fee_base():
    receivable = ReceivableBreakdown(
        linehaul=Decimal("1000.00"),
        same_day_submission=True,
    )
    result = calculate_factoring_fee_deduction(receivable)
    assert result.eligible_amount == Decimal("997.50")
    assert result.fee_amount == Decimal("29.93")
    assert result.reserve_amount == Decimal("99.75")
    assert result.advance_amount == Decimal("867.82")


def test_high_risk_and_non_recourse_surcharges_apply():
    receivable = ReceivableBreakdown(linehaul=Decimal("1000.00"), high_risk_customer=True)
    terms = FactoringTerms(non_recourse=True)
    result = calculate_factoring_fee_deduction(receivable, terms)
    assert result.fee_amount == Decimal("45.00")
    assert result.advance_amount == Decimal("855.00")


def test_fee_rate_is_capped_at_maximum():
    receivable = ReceivableBreakdown(linehaul=Decimal("1000.00"), high_risk_customer=True)
    terms = FactoringTerms(base_fee_rate=Decimal("0.0750"), non_recourse=True)
    result = calculate_factoring_fee_deduction(receivable, terms)
    assert result.fee_amount == Decimal("80.00")
    assert result.advance_amount == Decimal("820.00")


def test_credit_hold_blocks_funding_entirely():
    receivable = ReceivableBreakdown(
        linehaul=Decimal("1000.00"),
        fuel_surcharge=Decimal("100.00"),
        on_credit_hold=True,
    )
    result = calculate_factoring_fee_deduction(receivable)
    assert result.eligible_amount == Decimal("0.00")
    assert result.fee_amount == Decimal("0.00")
    assert result.reserve_amount == Decimal("0.00")
    assert result.advance_amount == Decimal("0.00")


def test_minimum_advance_boundary_blocks_small_funding():
    receivable = ReceivableBreakdown(linehaul=Decimal("286.00"))
    result = calculate_factoring_fee_deduction(receivable)
    assert result.eligible_amount == Decimal("286.00")
    assert result.fee_amount == Decimal("0.00")
    assert result.reserve_amount == Decimal("0.00")
    assert result.advance_amount == Decimal("0.00")


def test_negative_money_input_is_rejected():
    with pytest.raises(ValueError):
        calculate_factoring_fee_deduction(ReceivableBreakdown(linehaul=Decimal("-1.00")))
