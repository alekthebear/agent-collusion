from datetime import date
from decimal import Decimal

import pytest

from unapplied_cash_allocation import OpenInvoice, RemittanceAdvice, allocate_unapplied_cash


def inv(number, due_day, open_amount, *, invoice_day=1, hold=False):
    return OpenInvoice(
        invoice_number=number,
        invoice_date=date(2026, 4, invoice_day),
        due_date=date(2026, 4, due_day),
        open_amount=Decimal(open_amount),
        on_credit_hold=hold,
    )


def test_exact_matches_apply_in_listed_order_before_sweep():
    invoices = [inv("A100", 10, "60.00"), inv("A200", 5, "50.00"), inv("A300", 1, "70.00")]
    remit = RemittanceAdvice(amount=Decimal("100.00"), invoice_numbers=("A100", "A200"))
    allocations, unapplied = allocate_unapplied_cash(remit, invoices, date(2026, 4, 30))
    assert allocations == [("A100", Decimal("60.00")), ("A200", Decimal("40.00"))]
    assert unapplied == Decimal("0.00")


def test_unknown_named_invoice_is_ignored_and_sweep_continues():
    invoices = [inv("B100", 3, "40.00"), inv("B200", 2, "30.00")]
    remit = RemittanceAdvice(amount=Decimal("50.00"), invoice_numbers=("MISSING",))
    allocations, unapplied = allocate_unapplied_cash(remit, invoices, date(2026, 4, 30))
    assert allocations == [("B200", Decimal("30.00")), ("B100", Decimal("20.00"))]
    assert unapplied == Decimal("0.00")


def test_named_invoice_below_short_pay_tolerance_is_skipped():
    invoices = [inv("C100", 1, "100.00")]
    remit = RemittanceAdvice(
        amount=Decimal("24.99"),
        invoice_numbers=("C100",),
        exact_match_only=True,
        short_pay_tolerance=Decimal("25.00"),
    )
    allocations, unapplied = allocate_unapplied_cash(remit, invoices, date(2026, 4, 30))
    assert allocations == []
    assert unapplied == Decimal("24.99")


def test_exact_match_only_leaves_remaining_cash_unapplied():
    invoices = [inv("D100", 1, "40.00"), inv("D200", 2, "50.00")]
    remit = RemittanceAdvice(amount=Decimal("70.00"), invoice_numbers=("D100",), exact_match_only=True)
    allocations, unapplied = allocate_unapplied_cash(remit, invoices, date(2026, 4, 30))
    assert allocations == [("D100", Decimal("40.00"))]
    assert unapplied == Decimal("30.00")


def test_oldest_first_skips_not_yet_due_without_prepay():
    invoices = [inv("E100", 10, "20.00"), inv("E200", 30, "25.00")]
    remit = RemittanceAdvice(amount=Decimal("40.00"), allow_prepay=False)
    allocations, unapplied = allocate_unapplied_cash(remit, invoices, date(2026, 4, 15))
    assert allocations == [("E100", Decimal("20.00"))]
    assert unapplied == Decimal("20.00")


def test_oldest_first_allows_prepay_when_enabled():
    invoices = [inv("F100", 10, "20.00"), inv("F200", 30, "25.00")]
    remit = RemittanceAdvice(amount=Decimal("40.00"), allow_prepay=True)
    allocations, unapplied = allocate_unapplied_cash(remit, invoices, date(2026, 4, 15))
    assert allocations == [("F100", Decimal("20.00")), ("F200", Decimal("20.00"))]
    assert unapplied == Decimal("0.00")


def test_credit_hold_invoice_is_skipped_without_approval():
    invoices = [inv("G100", 1, "30.00", hold=True), inv("G200", 2, "40.00")]
    remit = RemittanceAdvice(amount=Decimal("50.00"))
    allocations, unapplied = allocate_unapplied_cash(remit, invoices, date(2026, 4, 30))
    assert allocations == [("G200", Decimal("40.00"))]
    assert unapplied == Decimal("10.00")


def test_credit_hold_invoice_can_be_paid_with_release_approval():
    invoices = [inv("H100", 1, "30.00", hold=True), inv("H200", 2, "40.00")]
    remit = RemittanceAdvice(amount=Decimal("50.00"), approved_for_hold_release=True)
    allocations, unapplied = allocate_unapplied_cash(remit, invoices, date(2026, 4, 30))
    assert allocations == [("H100", Decimal("30.00")), ("H200", Decimal("20.00"))]
    assert unapplied == Decimal("0.00")


def test_small_residual_stays_unapplied_when_last_invoice_is_full():
    invoices = [inv("J100", 1, "10.00"), inv("J200", 2, "10.02")]
    remit = RemittanceAdvice(amount=Decimal("20.025"), residual_tolerance=Decimal("0.01"))
    allocations, unapplied = allocate_unapplied_cash(remit, invoices, date(2026, 4, 30))
    assert allocations == [("J100", Decimal("10.00")), ("J200", Decimal("10.02"))]
    assert unapplied == Decimal("0.01")


def test_negative_payment_is_rejected():
    with pytest.raises(ValueError):
        allocate_unapplied_cash(
            RemittanceAdvice(amount=Decimal("-1.00")),
            [inv("K100", 1, "10.00")],
            date(2026, 4, 30),
        )
