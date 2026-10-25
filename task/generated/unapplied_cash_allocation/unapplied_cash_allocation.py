"""Allocate unapplied cash across a customer's open invoices.

Business rules:
- Cash application works from a remittance record and the customer's open invoices.
- If the remittance names invoice numbers, those exact matches are honored first in the
  listed order. Unknown invoice numbers are ignored.
- A named invoice must receive at least its short-pay tolerance to be applied at all;
  tiny residuals stay unapplied rather than creating nuisance partials.
- After exact matches, any remaining cash may sweep oldest-first when the remittance
  allows it. Invoices on credit hold are skipped unless the payment is marked as
  approved for hold release.
- Oldest-first also skips invoices not yet due when ``allow_prepay`` is false.
- No invoice may receive more than its open balance. Negative or zero open balances are
  ignored.
- If cash left after full invoices is within the residual tolerance, it is added to the
  last applied invoice, but never above that invoice's open balance; otherwise it stays
  unapplied.
- Amounts are rounded to cents using half-up rounding.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
DEFAULT_SHORT_PAY_TOLERANCE = Decimal("25.00")
DEFAULT_RESIDUAL_TOLERANCE = Decimal("1.00")


@dataclass(frozen=True)
class OpenInvoice:
    invoice_number: str
    invoice_date: date
    due_date: date
    open_amount: Decimal
    on_credit_hold: bool = False


@dataclass(frozen=True)
class RemittanceAdvice:
    amount: Decimal
    invoice_numbers: tuple[str, ...] = ()
    exact_match_only: bool = False
    allow_prepay: bool = False
    approved_for_hold_release: bool = False
    short_pay_tolerance: Decimal = DEFAULT_SHORT_PAY_TOLERANCE
    residual_tolerance: Decimal = DEFAULT_RESIDUAL_TOLERANCE


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate(remit: RemittanceAdvice) -> None:
    if remit.amount < Decimal("0"):
        raise ValueError("amount cannot be negative")
    if remit.short_pay_tolerance < Decimal("0"):
        raise ValueError("short_pay_tolerance cannot be negative")
    if remit.residual_tolerance < Decimal("0"):
        raise ValueError("residual_tolerance cannot be negative")


def _eligible(invoice: OpenInvoice, remit: RemittanceAdvice, as_of: date) -> bool:
    if invoice.open_amount <= Decimal("0"):
        return False
    if invoice.on_credit_hold and not remit.approved_for_hold_release:
        return False
    if not remit.allow_prepay and invoice.due_date > as_of:
        return False
    return True


def allocate_unapplied_cash(
    remit: RemittanceAdvice, invoices: list[OpenInvoice], as_of: date
) -> tuple[list[tuple[str, Decimal]], Decimal]:
    """Return allocations and unapplied remainder, all rounded to cents."""
    _validate(remit)
    remaining = _money(remit.amount)
    if remaining == Decimal("0.00"):
        return [], Decimal("0.00")

    by_number = {inv.invoice_number: inv for inv in invoices}
    open_by_number = {inv.invoice_number: _money(inv.open_amount) for inv in invoices}
    allocations: list[tuple[str, Decimal]] = []

    for number in remit.invoice_numbers:
        inv = by_number.get(number)
        if inv is None or open_by_number.get(number, Decimal("0.00")) <= Decimal("0.00"):
            continue
        if inv.on_credit_hold and not remit.approved_for_hold_release:
            continue
        minimum = min(_money(remit.short_pay_tolerance), open_by_number[number])
        if remaining < minimum:
            continue
        applied = min(remaining, open_by_number[number])
        applied = _money(applied)
        allocations.append((number, applied))
        open_by_number[number] -= applied
        remaining -= applied
        if remaining == Decimal("0.00"):
            return allocations, Decimal("0.00")

    if not remit.exact_match_only and remaining > Decimal("0.00"):
        sweep = sorted(invoices, key=lambda inv: (inv.due_date, inv.invoice_date, inv.invoice_number))
        for inv in sweep:
            if not _eligible(inv, remit, as_of):
                continue
            open_amount = open_by_number[inv.invoice_number]
            if open_amount <= Decimal("0.00"):
                continue
            applied = min(remaining, open_amount)
            applied = _money(applied)
            allocations.append((inv.invoice_number, applied))
            open_by_number[inv.invoice_number] -= applied
            remaining -= applied
            if remaining == Decimal("0.00"):
                break

    if allocations and Decimal("0.00") < remaining <= _money(remit.residual_tolerance):
        last_number, last_amount = allocations[-1]
        room = open_by_number[last_number]
        bump = min(remaining, room)
        if bump > Decimal("0.00"):
            bump = _money(bump)
            allocations[-1] = (last_number, _money(last_amount + bump))
            remaining -= bump

    return allocations, _money(remaining)
