"""Customer invoice lines and totals for settled loads.

Each charge on a load becomes one invoice line: quantity times unit rate (miles x
rate per mile, hours x detention rate, pallets x handling rate). Rates in the rate
engine carry up to four decimal places, so line amounts are rounded to the cent,
half up, before they are printed.

Customers on quick-pay terms get a 2% discount for paying within 10 days; it is
printed as its own negative line under the subtotal.

Customer AP systems (Hartline's included) reconcile every invoice by adding up the
printed lines, so the subtotal must equal the sum of the line amounts as printed.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
QUICK_PAY_RATE = Decimal("0.02")


@dataclass(frozen=True)
class Charge:
    description: str
    quantity: Decimal
    unit_rate: Decimal


@dataclass(frozen=True)
class InvoiceLine:
    description: str
    amount: Decimal


@dataclass(frozen=True)
class Invoice:
    lines: list[InvoiceLine]
    subtotal: Decimal
    quick_pay_discount: Decimal
    total: Decimal


def _to_cents(amount: Decimal) -> Decimal:
    # ROUND_HALF_UP rounds away from zero, so credits round the same way as charges.
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _extended(charge: Charge) -> Decimal:
    """Quantity times rate, unrounded."""
    return Decimal(charge.quantity) * Decimal(charge.unit_rate)


def _printed_lines(charges: list[Charge]) -> list[InvoiceLine]:
    return [InvoiceLine(charge.description, _to_cents(_extended(charge))) for charge in charges]


def _quick_pay_discount(subtotal: Decimal) -> Decimal:
    return _to_cents(subtotal * QUICK_PAY_RATE)


def build_invoice(charges: list[Charge], quick_pay: bool = False) -> Invoice:
    """Build the printed invoice for one load's charges.

    Credits (negative unit rates) are allowed. With ``quick_pay``, a 2% discount
    of the subtotal is taken off the total.
    """
    if not charges:
        raise ValueError("an invoice needs at least one charge")
    lines = _printed_lines(charges)
    subtotal = sum((line.amount for line in lines), Decimal("0.00"))
    discount = _quick_pay_discount(subtotal) if quick_pay else Decimal("0.00")
    return Invoice(
        lines=lines,
        subtotal=subtotal,
        quick_pay_discount=discount,
        total=subtotal - discount,
    )
