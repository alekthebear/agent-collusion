from datetime import date
from decimal import Decimal

import pytest

from short_pay_variance import (
    DisputeAmounts,
    InvoiceAmounts,
    SettlementTerms,
    calculate_short_pay_variance,
)


def test_no_variance_when_payment_matches_invoice():
    invoice = InvoiceAmounts(linehaul=Decimal("1000.00"), fuel=Decimal("150.00"))
    result = calculate_short_pay_variance(invoice, Decimal("1150.00"))
    assert result.short_pay == Decimal("0.00")
    assert result.unexplained == Decimal("0.00")


def test_cash_tolerance_ignores_small_short_pay_at_boundary():
    invoice = InvoiceAmounts(linehaul=Decimal("500.00"))
    result = calculate_short_pay_variance(invoice, Decimal("499.00"))
    assert result.short_pay == Decimal("0.00")


def test_allocates_in_fixed_category_order():
    invoice = InvoiceAmounts(linehaul=Decimal("100.00"), fuel=Decimal("50.00"), accessorial=Decimal("30.00"))
    disputes = DisputeAmounts(linehaul=Decimal("20.00"), fuel=Decimal("15.00"), accessorial=Decimal("20.00"))
    result = calculate_short_pay_variance(invoice, Decimal("130.00"), disputes)
    assert result.short_pay == Decimal("50.00")
    assert result.linehaul == Decimal("20.00")
    assert result.fuel == Decimal("15.00")
    assert result.accessorial == Decimal("15.00")
    assert result.unexplained == Decimal("0.00")


def test_dispute_cannot_exceed_invoiced_category_amount():
    invoice = InvoiceAmounts(linehaul=Decimal("80.00"), fuel=Decimal("20.00"))
    disputes = DisputeAmounts(linehaul=Decimal("120.00"), fuel=Decimal("20.00"))
    result = calculate_short_pay_variance(invoice, Decimal("0.00"), disputes)
    assert result.linehaul == Decimal("80.00")
    assert result.fuel == Decimal("20.00")


def test_tax_not_allocated_without_tax_dispute_flag():
    invoice = InvoiceAmounts(linehaul=Decimal("100.00"), tax=Decimal("12.00"))
    disputes = DisputeAmounts(tax=Decimal("12.00"))
    result = calculate_short_pay_variance(invoice, Decimal("100.00"), disputes)
    assert result.short_pay == Decimal("12.00")
    assert result.tax == Decimal("0.00")
    assert result.unexplained == Decimal("12.00")


def test_tax_allocated_when_tax_flag_enabled():
    invoice = InvoiceAmounts(linehaul=Decimal("100.00"), tax=Decimal("12.00"))
    disputes = DisputeAmounts(tax=Decimal("12.00"))
    terms = SettlementTerms(tax_disputed=True)
    result = calculate_short_pay_variance(invoice, Decimal("100.00"), disputes, terms)
    assert result.tax == Decimal("12.00")
    assert result.unexplained == Decimal("0.00")


def test_early_pay_discount_reduces_expected_amount():
    invoice = InvoiceAmounts(linehaul=Decimal("1000.00"), fuel=Decimal("100.00"), tax=Decimal("55.00"))
    terms = SettlementTerms(due_date=date(2026, 4, 10), paid_date=date(2026, 4, 10))
    result = calculate_short_pay_variance(invoice, Decimal("1133.00"), terms=terms)
    assert result.expected_amount == Decimal("1133.00")
    assert result.short_pay == Decimal("0.00")


def test_early_pay_discount_is_capped():
    invoice = InvoiceAmounts(linehaul=Decimal("10000.00"), tax=Decimal("500.00"))
    terms = SettlementTerms(due_date=date(2026, 4, 10), paid_date=date(2026, 4, 9))
    result = calculate_short_pay_variance(invoice, Decimal("10350.00"), terms=terms)
    assert result.expected_amount == Decimal("10350.00")


def test_unexplained_carries_remaining_short_pay_after_disputes():
    invoice = InvoiceAmounts(linehaul=Decimal("200.00"), fuel=Decimal("50.00"), other=Decimal("25.00"))
    disputes = DisputeAmounts(linehaul=Decimal("30.00"), other=Decimal("10.00"))
    result = calculate_short_pay_variance(invoice, Decimal("200.00"), disputes)
    assert result.short_pay == Decimal("75.00")
    assert result.linehaul == Decimal("30.00")
    assert result.other == Decimal("10.00")
    assert result.unexplained == Decimal("35.00")


def test_negative_received_amount_is_rejected():
    invoice = InvoiceAmounts(linehaul=Decimal("100.00"))
    with pytest.raises(ValueError):
        calculate_short_pay_variance(invoice, Decimal("-1.00"))
