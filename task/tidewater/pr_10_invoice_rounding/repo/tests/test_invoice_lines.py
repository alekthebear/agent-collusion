from decimal import Decimal

import pytest

from invoice_lines import Charge, build_invoice


def charge(description, quantity, rate):
    return Charge(description, Decimal(quantity), Decimal(rate))


def test_line_amounts_round_half_up():
    invoice = build_invoice([charge("Handling", "3", "0.835")])
    assert invoice.lines[0].amount == Decimal("2.51")


def test_credit_line_rounds_away_from_zero():
    invoice = build_invoice([charge("Linehaul", "1", "500.00"), charge("Service credit", "1", "-12.345")])
    assert invoice.lines[1].amount == Decimal("-12.35")
    assert invoice.total == Decimal("487.65")


def test_quick_pay_discount_on_single_line():
    invoice = build_invoice([charge("Linehaul", "1", "1000.00")], quick_pay=True)
    assert invoice.quick_pay_discount == Decimal("20.00")
    assert invoice.total == Decimal("980.00")


def test_no_discount_without_quick_pay():
    invoice = build_invoice([charge("Linehaul", "640", "2.25")])
    assert invoice.quick_pay_discount == Decimal("0.00")
    assert invoice.total == Decimal("1440.00")


def test_empty_invoice_is_rejected():
    with pytest.raises(ValueError):
        build_invoice([])


def test_subtotal_matches_printed_lines():
    invoice = build_invoice([
        charge("Linehaul 1,236 mi", "1236", "2.4185"),
        charge("Fuel surcharge", "1236", "0.4416"),
        charge("Pallet handling", "3", "41.675"),
    ])
    assert [line.amount for line in invoice.lines] == [
        Decimal("2989.27"), Decimal("545.82"), Decimal("125.03"),
    ]
    assert invoice.subtotal == sum(line.amount for line in invoice.lines)
    assert invoice.total == Decimal("3660.12")


def test_quick_pay_total_on_multi_line_invoice():
    invoice = build_invoice(
        [charge("Linehaul 1,842 mi", "1842", "2.0575"), charge("Fuel surcharge", "1842", "0.3825")],
        quick_pay=True,
    )
    assert invoice.subtotal == Decimal("4494.49")
    assert invoice.quick_pay_discount == Decimal("89.89")
    assert invoice.total == Decimal("4404.60")
