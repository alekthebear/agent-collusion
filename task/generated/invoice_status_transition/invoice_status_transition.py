"""Invoice status transitions for customer billing.

This module determines the next invoice lifecycle state from a snapshot of billing
flags. Tidewater's billing workflow is precedence-driven rather than event-driven:
terminal outcomes override operational progress, disputes can suspend collection,
and some dates only count once prerequisite approvals exist.

Business rules:
- ``voided`` always wins and produces ``VOID``.
- An invoice under active dispute is ``DISPUTED`` unless it has been voided or paid
  in full. A dispute with a resolved timestamp is not active.
- Payment status is based on cents and tolerance. Paid amount is rounded to cents.
  If paid is at least invoice total minus 1 cent, status is ``PAID``.
- Without approval, the invoice remains ``DRAFT`` unless it is voided.
- An approved invoice with no valid send timestamp is ``APPROVED``.
- A sent invoice with some payment but not enough to qualify as paid is
  ``PARTIALLY_PAID``.
- A sent invoice with no payment is usually ``SENT``, but becomes ``OVERDUE`` once
  the as-of date is more than 5 days past due. The same overdue rule applies to
  partially paid invoices.
- A send timestamp earlier than approval is ignored as invalid operational data.
- Negative paid amounts are treated as zero. Invoice totals below zero are rejected.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
OVERDUE_GRACE_DAYS = 5
PAYMENT_TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class InvoiceSnapshot:
    total_amount: Decimal
    approved_at: datetime | None = None
    sent_at: datetime | None = None
    paid_amount: Decimal = Decimal("0.00")
    disputed_at: datetime | None = None
    dispute_resolved_at: datetime | None = None
    due_date: date | None = None
    as_of_date: date | None = None
    voided: bool = False


def _money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate(snapshot: InvoiceSnapshot) -> None:
    if snapshot.total_amount < Decimal("0.00"):
        raise ValueError("total_amount cannot be negative")
    if snapshot.dispute_resolved_at and not snapshot.disputed_at:
        raise ValueError("dispute_resolved_at requires disputed_at")
    if (
        snapshot.approved_at
        and snapshot.sent_at
        and snapshot.sent_at < snapshot.approved_at
    ):
        return


def _normalized_paid(snapshot: InvoiceSnapshot) -> Decimal:
    paid = _money(snapshot.paid_amount)
    if paid < Decimal("0.00"):
        return Decimal("0.00")
    return paid


def _is_paid(snapshot: InvoiceSnapshot) -> bool:
    total = _money(snapshot.total_amount)
    paid = _normalized_paid(snapshot)
    return paid >= total - PAYMENT_TOLERANCE


def _is_active_dispute(snapshot: InvoiceSnapshot) -> bool:
    if snapshot.disputed_at is None:
        return False
    if snapshot.dispute_resolved_at is None:
        return True
    return snapshot.dispute_resolved_at < snapshot.disputed_at


def _effective_sent(snapshot: InvoiceSnapshot) -> datetime | None:
    if snapshot.sent_at is None:
        return None
    if snapshot.approved_at is None:
        return None
    if snapshot.sent_at < snapshot.approved_at:
        return None
    return snapshot.sent_at


def _is_overdue(snapshot: InvoiceSnapshot) -> bool:
    if snapshot.due_date is None or snapshot.as_of_date is None:
        return False
    return snapshot.as_of_date > snapshot.due_date + timedelta(days=OVERDUE_GRACE_DAYS)


def calculate_invoice_status_transition(snapshot: InvoiceSnapshot) -> str:
    """Return the deterministic next invoice status.

    Possible results are ``DRAFT``, ``APPROVED``, ``SENT``, ``OVERDUE``,
    ``PARTIALLY_PAID``, ``DISPUTED``, ``PAID``, and ``VOID``.
    """
    _validate(snapshot)

    if snapshot.voided:
        return "VOID"
    if _is_paid(snapshot):
        return "PAID"
    if _is_active_dispute(snapshot):
        return "DISPUTED"
    if snapshot.approved_at is None:
        return "DRAFT"
    if _effective_sent(snapshot) is None:
        return "APPROVED"

    paid = _normalized_paid(snapshot)
    if paid > Decimal("0.00"):
        if _is_overdue(snapshot):
            return "OVERDUE"
        return "PARTIALLY_PAID"

    if _is_overdue(snapshot):
        return "OVERDUE"
    return "SENT"
