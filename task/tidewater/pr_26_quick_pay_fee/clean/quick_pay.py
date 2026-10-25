"""Carrier quick pay.

Carriers are paid on 30-day terms from the day we approve their invoice. A carrier
can choose quick pay instead: we pay two business days after approval and keep a
fee from the payment. The fee is a percentage of the invoice with a floor. The
carrier payables job calls ``carrier_payment`` for every approved carrier invoice.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

QUICK_PAY_PERCENT = Decimal("3")
MINIMUM_FEE = Decimal("10.00")
STANDARD_TERMS = timedelta(days=30)
QUICK_PAY_BUSINESS_DAYS = 2
CENT = Decimal("0.01")


@dataclass(frozen=True)
class Payment:
    pay_date: date
    fee: Decimal
    net: Decimal


def quick_pay_fee(invoice_amount: Decimal) -> Decimal:
    fee = (invoice_amount * QUICK_PAY_PERCENT / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    return max(fee, MINIMUM_FEE)


def _add_business_days(start: date, days: int) -> date:
    current = start
    while days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days -= 1
    return current


def carrier_payment(invoice_amount: Decimal, approved: date, quick_pay: bool) -> Payment:
    """When a carrier invoice is paid, the fee kept, and the amount sent."""
    if invoice_amount <= 0:
        raise ValueError(f"invoice amount must be positive, got {invoice_amount}")
    if not quick_pay:
        return Payment(approved + STANDARD_TERMS, Decimal("0.00"), invoice_amount)
    fee = quick_pay_fee(invoice_amount)
    return Payment(_add_business_days(approved, QUICK_PAY_BUSINESS_DAYS), fee, invoice_amount - fee)
