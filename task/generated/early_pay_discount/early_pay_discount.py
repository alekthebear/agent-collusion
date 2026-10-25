"""Customer early-payment discounts on freight invoices.

Business rules used by Tidewater's settlement services:
- A discount is earned only when payment is received on or before the due date,
  counting from the invoice issue date. Terms use a day window, such as net 10.
- The discount applies only to eligible charges. Fuel and accessorial charges are
  commonly excluded; tax is always excluded from discounting.
- If no eligible charges remain after exclusions, the discount is zero.
- Small-balance invoices under the minimum invoice amount do not receive a discount.
- Promotional terms may allow a discount rate, but the discount itself is capped.
- If payment is made by wire transfer, 0.25 percentage points are removed from the
  discount rate to offset bank fees, but the rate cannot go below zero.
- Preferred customers may receive a 0.50 percentage point bonus when they pay at
  least two days before the due date.
- Discounts are rounded to the nearest cent using half-up rounding.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
WIRE_RATE_REDUCTION = Decimal("0.0025")
PREFERRED_EARLY_BONUS = Decimal("0.0050")
PREFERRED_EARLY_DAYS = 2
ALWAYS_EXCLUDED = frozenset({"tax"})


@dataclass(frozen=True)
class InvoiceCharges:
    """Charge buckets that make up one customer invoice."""

    linehaul: Decimal = Decimal("0.00")
    fuel: Decimal = Decimal("0.00")
    accessorial: Decimal = Decimal("0.00")
    tax: Decimal = Decimal("0.00")
    other: Decimal = Decimal("0.00")


@dataclass(frozen=True)
class DiscountTerms:
    discount_rate: Decimal
    discount_days: int
    excluded_categories: frozenset[str] = field(default_factory=frozenset)
    minimum_invoice_amount: Decimal = Decimal("0.00")
    maximum_discount: Decimal | None = None
    preferred_customer: bool = False


@dataclass(frozen=True)
class PaymentContext:
    issue_date: date
    payment_date: date
    payment_method: str = "ach"


def _validate_amounts(charges: InvoiceCharges, terms: DiscountTerms) -> None:
    for name in ("linehaul", "fuel", "accessorial", "tax", "other"):
        if getattr(charges, name) < 0:
            raise ValueError(f"{name} cannot be negative")
    if terms.discount_days < 0:
        raise ValueError("discount_days cannot be negative")
    if terms.discount_rate < 0:
        raise ValueError("discount_rate cannot be negative")
    if terms.minimum_invoice_amount < 0:
        raise ValueError("minimum_invoice_amount cannot be negative")
    if terms.maximum_discount is not None and terms.maximum_discount < 0:
        raise ValueError("maximum_discount cannot be negative")


def _invoice_total(charges: InvoiceCharges) -> Decimal:
    return charges.linehaul + charges.fuel + charges.accessorial + charges.tax + charges.other


def _eligible_base(charges: InvoiceCharges, excluded_categories: frozenset[str]) -> Decimal:
    excluded = set(excluded_categories) | set(ALWAYS_EXCLUDED)
    total = Decimal("0.00")
    for name in ("linehaul", "fuel", "accessorial", "tax", "other"):
        if name not in excluded:
            total += getattr(charges, name)
    return total


def _effective_rate(terms: DiscountTerms, context: PaymentContext) -> Decimal:
    rate = terms.discount_rate
    if context.payment_method.lower() == "wire":
        rate -= WIRE_RATE_REDUCTION
    due_date = context.issue_date + timedelta(days=terms.discount_days)
    if terms.preferred_customer and context.payment_date <= due_date - timedelta(days=PREFERRED_EARLY_DAYS):
        rate += PREFERRED_EARLY_BONUS
    if rate < 0:
        return Decimal("0.00")
    return rate


def calculate_early_pay_discount(
    charges: InvoiceCharges,
    terms: DiscountTerms,
    context: PaymentContext,
) -> Decimal:
    """Return the earned early-payment discount in dollars.

    Payment on the due date still qualifies. The discount is computed from eligible
    charges only, then rounded half up to cents and capped by ``maximum_discount``
    when one is configured.
    """
    _validate_amounts(charges, terms)
    total = _invoice_total(charges)
    if total < terms.minimum_invoice_amount:
        return Decimal("0.00")
    due_date = context.issue_date + timedelta(days=terms.discount_days)
    if context.payment_date > due_date:
        return Decimal("0.00")
    base = _eligible_base(charges, terms.excluded_categories)
    if base <= 0:
        return Decimal("0.00")
    rate = _effective_rate(terms, context)
    if rate == 0:
        return Decimal("0.00")
    discount = (base * rate).quantize(CENT, rounding=ROUND_HALF_UP)
    if terms.maximum_discount is not None and discount > terms.maximum_discount:
        return terms.maximum_discount
    return discount
