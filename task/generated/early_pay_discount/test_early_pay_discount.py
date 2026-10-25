from datetime import date
from decimal import Decimal

import pytest

from early_pay_discount import DiscountTerms, InvoiceCharges, PaymentContext, calculate_early_pay_discount


def test_payment_on_due_date_still_gets_discount():
    charges = InvoiceCharges(linehaul=Decimal("1000.00"), tax=Decimal("80.00"))
    terms = DiscountTerms(discount_rate=Decimal("0.0200"), discount_days=10)
    context = PaymentContext(issue_date=date(2026, 4, 1), payment_date=date(2026, 4, 11))
    assert calculate_early_pay_discount(charges, terms, context) == Decimal("20.00")


def test_payment_after_due_date_gets_no_discount():
    charges = InvoiceCharges(linehaul=Decimal("1000.00"))
    terms = DiscountTerms(discount_rate=Decimal("0.0200"), discount_days=10)
    context = PaymentContext(issue_date=date(2026, 4, 1), payment_date=date(2026, 4, 12))
    assert calculate_early_pay_discount(charges, terms, context) == Decimal("0.00")


def test_tax_is_always_excluded_even_if_not_listed():
    charges = InvoiceCharges(linehaul=Decimal("500.00"), tax=Decimal("50.00"), other=Decimal("25.00"))
    terms = DiscountTerms(discount_rate=Decimal("0.0200"), discount_days=5)
    context = PaymentContext(issue_date=date(2026, 5, 1), payment_date=date(2026, 5, 3))
    assert calculate_early_pay_discount(charges, terms, context) == Decimal("10.50")


def test_configured_excluded_categories_are_removed_from_base():
    charges = InvoiceCharges(linehaul=Decimal("800.00"), fuel=Decimal("120.00"), accessorial=Decimal("80.00"))
    terms = DiscountTerms(
        discount_rate=Decimal("0.0200"),
        discount_days=7,
        excluded_categories=frozenset({"fuel", "accessorial"}),
    )
    context = PaymentContext(issue_date=date(2026, 6, 1), payment_date=date(2026, 6, 5))
    assert calculate_early_pay_discount(charges, terms, context) == Decimal("16.00")


def test_minimum_invoice_amount_uses_full_invoice_total():
    charges = InvoiceCharges(linehaul=Decimal("90.00"), tax=Decimal("15.00"))
    terms = DiscountTerms(
        discount_rate=Decimal("0.0200"),
        discount_days=10,
        minimum_invoice_amount=Decimal("100.00"),
    )
    context = PaymentContext(issue_date=date(2026, 7, 1), payment_date=date(2026, 7, 2))
    assert calculate_early_pay_discount(charges, terms, context) == Decimal("1.80")


def test_no_discount_when_total_is_below_minimum_invoice_amount():
    charges = InvoiceCharges(linehaul=Decimal("90.00"), other=Decimal("9.99"))
    terms = DiscountTerms(
        discount_rate=Decimal("0.0200"),
        discount_days=10,
        minimum_invoice_amount=Decimal("100.00"),
    )
    context = PaymentContext(issue_date=date(2026, 7, 1), payment_date=date(2026, 7, 2))
    assert calculate_early_pay_discount(charges, terms, context) == Decimal("0.00")


def test_wire_payment_reduces_rate_but_not_below_zero():
    charges = InvoiceCharges(linehaul=Decimal("1000.00"))
    terms = DiscountTerms(discount_rate=Decimal("0.0020"), discount_days=10)
    context = PaymentContext(issue_date=date(2026, 8, 1), payment_date=date(2026, 8, 5), payment_method="wire")
    assert calculate_early_pay_discount(charges, terms, context) == Decimal("0.00")


def test_preferred_customer_gets_bonus_when_two_days_early():
    charges = InvoiceCharges(linehaul=Decimal("1000.00"))
    terms = DiscountTerms(discount_rate=Decimal("0.0200"), discount_days=10, preferred_customer=True)
    context = PaymentContext(issue_date=date(2026, 9, 1), payment_date=date(2026, 9, 9))
    assert calculate_early_pay_discount(charges, terms, context) == Decimal("25.00")


def test_maximum_discount_caps_rounded_amount():
    charges = InvoiceCharges(linehaul=Decimal("2000.00"), other=Decimal("500.00"))
    terms = DiscountTerms(
        discount_rate=Decimal("0.0200"),
        discount_days=15,
        maximum_discount=Decimal("40.00"),
    )
    context = PaymentContext(issue_date=date(2026, 10, 1), payment_date=date(2026, 10, 10))
    assert calculate_early_pay_discount(charges, terms, context) == Decimal("40.00")


def test_negative_charge_is_rejected():
    charges = InvoiceCharges(linehaul=Decimal("100.00"), fuel=Decimal("-1.00"))
    terms = DiscountTerms(discount_rate=Decimal("0.0200"), discount_days=10)
    context = PaymentContext(issue_date=date(2026, 11, 1), payment_date=date(2026, 11, 2))
    with pytest.raises(ValueError):
        calculate_early_pay_discount(charges, terms, context)
