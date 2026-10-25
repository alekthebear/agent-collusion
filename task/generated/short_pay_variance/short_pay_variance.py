"""Short-pay variance allocation for customer invoice settlement.

A short pay happens when the customer remits less than the invoiced amount. Settlement
needs a consistent way to split the underpayment between claimed disputes and any
unexplained remainder. Tidewater applies these rules:

* If payment meets or exceeds the invoice, there is no short-pay variance.
* A small remittance difference at or below the cash tolerance is ignored.
* Disputed categories may absorb variance only up to their disputed amount, rounded to
  the cent, in a fixed order: linehaul, fuel, accessorial, tax, other.
* Tax disputes are not allocated unless the customer explicitly disputes tax.
* If the payment came in before the due date, an early-pay discount may reduce the
  collectible invoice; the variance is measured against that reduced expectation.
* The early-pay discount is a percent of the invoice subtotal before tax and is capped.
* Any remaining short pay after category allocation is reported as unexplained.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
CATEGORY_ORDER = ("linehaul", "fuel", "accessorial", "tax", "other")


@dataclass(frozen=True)
class InvoiceAmounts:
    linehaul: Decimal
    fuel: Decimal = Decimal("0.00")
    accessorial: Decimal = Decimal("0.00")
    tax: Decimal = Decimal("0.00")
    other: Decimal = Decimal("0.00")


@dataclass(frozen=True)
class DisputeAmounts:
    linehaul: Decimal = Decimal("0.00")
    fuel: Decimal = Decimal("0.00")
    accessorial: Decimal = Decimal("0.00")
    tax: Decimal = Decimal("0.00")
    other: Decimal = Decimal("0.00")


@dataclass(frozen=True)
class SettlementTerms:
    cash_tolerance: Decimal = Decimal("1.00")
    early_pay_discount_percent: Decimal = Decimal("2.00")
    early_pay_discount_cap: Decimal = Decimal("150.00")
    due_date: date | None = None
    paid_date: date | None = None
    tax_disputed: bool = False


@dataclass(frozen=True)
class VarianceResult:
    expected_amount: Decimal
    received_amount: Decimal
    short_pay: Decimal
    linehaul: Decimal
    fuel: Decimal
    accessorial: Decimal
    tax: Decimal
    other: Decimal
    unexplained: Decimal


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate_nonnegative(amounts: InvoiceAmounts | DisputeAmounts) -> None:
    for name in CATEGORY_ORDER:
        if getattr(amounts, name) < 0:
            raise ValueError(f"{name} cannot be negative")


def _invoice_total(invoice: InvoiceAmounts) -> Decimal:
    return sum((_money(getattr(invoice, name)) for name in CATEGORY_ORDER), Decimal("0.00"))


def _early_pay_discount(invoice: InvoiceAmounts, terms: SettlementTerms) -> Decimal:
    if terms.due_date is None or terms.paid_date is None or terms.paid_date > terms.due_date:
        return Decimal("0.00")
    subtotal = invoice.linehaul + invoice.fuel + invoice.accessorial + invoice.other
    discount = _money(subtotal * terms.early_pay_discount_percent / Decimal("100"))
    return min(discount, _money(terms.early_pay_discount_cap))


def calculate_short_pay_variance(
    invoice: InvoiceAmounts,
    received_amount: Decimal,
    disputes: DisputeAmounts = DisputeAmounts(),
    terms: SettlementTerms = SettlementTerms(),
) -> VarianceResult:
    """Allocate a customer short pay across disputed categories and unexplained remainder."""
    _validate_nonnegative(invoice)
    _validate_nonnegative(disputes)
    received = _money(received_amount)
    if received < 0:
        raise ValueError("received_amount cannot be negative")

    gross_expected = _invoice_total(invoice)
    expected = _money(gross_expected - _early_pay_discount(invoice, terms))
    short_pay = _money(expected - received)
    if short_pay <= terms.cash_tolerance:
        short_pay = Decimal("0.00")
    if short_pay <= 0:
        return VarianceResult(expected, received, Decimal("0.00"), *(Decimal("0.00") for _ in range(6)))

    allocated: dict[str, Decimal] = {name: Decimal("0.00") for name in CATEGORY_ORDER}
    remaining = short_pay
    for name in CATEGORY_ORDER:
        if name == "tax" and not terms.tax_disputed:
            continue
        disputed = _money(getattr(disputes, name))
        invoiced = _money(getattr(invoice, name))
        capacity = min(disputed, invoiced)
        if capacity <= 0 or remaining <= 0:
            continue
        take = min(capacity, remaining)
        allocated[name] = take
        remaining = _money(remaining - take)

    return VarianceResult(
        expected_amount=expected,
        received_amount=received,
        short_pay=short_pay,
        linehaul=allocated["linehaul"],
        fuel=allocated["fuel"],
        accessorial=allocated["accessorial"],
        tax=allocated["tax"],
        other=allocated["other"],
        unexplained=remaining,
    )
