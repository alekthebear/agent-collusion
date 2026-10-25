from datetime import date, datetime
from decimal import Decimal

import pytest

from invoice_status_transition import InvoiceSnapshot, calculate_invoice_status_transition


def ts(day, hour=9, minute=0):
    return datetime(2026, 4, day, hour, minute)


def test_void_always_wins_over_other_flags():
    snapshot = InvoiceSnapshot(
        total_amount=Decimal("100.00"),
        approved_at=ts(1),
        sent_at=ts(2),
        paid_amount=Decimal("100.00"),
        disputed_at=ts(3),
        voided=True,
    )
    assert calculate_invoice_status_transition(snapshot) == "VOID"


def test_paid_within_one_cent_tolerance_is_paid():
    snapshot = InvoiceSnapshot(
        total_amount=Decimal("100.00"),
        approved_at=ts(1),
        sent_at=ts(2),
        paid_amount=Decimal("99.99"),
    )
    assert calculate_invoice_status_transition(snapshot) == "PAID"


def test_active_dispute_blocks_sent_status_when_not_paid():
    snapshot = InvoiceSnapshot(
        total_amount=Decimal("250.00"),
        approved_at=ts(1),
        sent_at=ts(2),
        disputed_at=ts(5),
        paid_amount=Decimal("0.00"),
    )
    assert calculate_invoice_status_transition(snapshot) == "DISPUTED"


def test_unapproved_invoice_stays_draft_even_if_sent_flag_exists():
    snapshot = InvoiceSnapshot(
        total_amount=Decimal("75.00"),
        sent_at=ts(2),
    )
    assert calculate_invoice_status_transition(snapshot) == "DRAFT"


def test_sent_before_approval_is_ignored_and_status_is_approved():
    snapshot = InvoiceSnapshot(
        total_amount=Decimal("75.00"),
        approved_at=ts(3),
        sent_at=ts(2),
    )
    assert calculate_invoice_status_transition(snapshot) == "APPROVED"


def test_partial_payment_before_overdue_is_partially_paid():
    snapshot = InvoiceSnapshot(
        total_amount=Decimal("200.00"),
        approved_at=ts(1),
        sent_at=ts(2),
        paid_amount=Decimal("50.00"),
        due_date=date(2026, 4, 10),
        as_of_date=date(2026, 4, 15),
    )
    assert calculate_invoice_status_transition(snapshot) == "PARTIALLY_PAID"


def test_overdue_starts_only_after_five_day_grace_period():
    snapshot = InvoiceSnapshot(
        total_amount=Decimal("200.00"),
        approved_at=ts(1),
        sent_at=ts(2),
        due_date=date(2026, 4, 10),
        as_of_date=date(2026, 4, 15),
    )
    assert calculate_invoice_status_transition(snapshot) == "SENT"


def test_unpaid_invoice_becomes_overdue_after_grace_period():
    snapshot = InvoiceSnapshot(
        total_amount=Decimal("200.00"),
        approved_at=ts(1),
        sent_at=ts(2),
        due_date=date(2026, 4, 10),
        as_of_date=date(2026, 4, 16),
    )
    assert calculate_invoice_status_transition(snapshot) == "OVERDUE"


def test_negative_paid_amount_is_treated_as_zero():
    snapshot = InvoiceSnapshot(
        total_amount=Decimal("90.00"),
        approved_at=ts(1),
        sent_at=ts(2),
        paid_amount=Decimal("-3.20"),
    )
    assert calculate_invoice_status_transition(snapshot) == "SENT"


def test_negative_total_amount_is_rejected():
    with pytest.raises(ValueError):
        calculate_invoice_status_transition(InvoiceSnapshot(total_amount=Decimal("-1.00")))
