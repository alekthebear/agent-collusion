"""Lumper reimbursement for unload services paid by drivers at receivers.

Tidewater reimburses documented lumper receipts to the carrier and bills the customer
under the load's pass-through terms. Standard rules are: receipts under the no-receipt
limit may be reimbursed without an image, but larger amounts require a receipt; tips,
parking and late fees are never reimbursable; a receipt total above the broker's
approval limit is reimbursed only up to that limit unless pre-approved; and tiny cash
rounding differences up to five cents are tolerated. The customer bill follows the
same approved base, with either pure pass-through or a percentage markup, and may be
capped by contract.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
DEFAULT_NO_RECEIPT_LIMIT = Decimal("25.00")
DEFAULT_APPROVAL_LIMIT = Decimal("300.00")
DEFAULT_MARKUP_RATE = Decimal("0.10")
DEFAULT_MAX_CUSTOMER_BILL = Decimal("500.00")
CASH_TOLERANCE = Decimal("0.05")


@dataclass(frozen=True)
class LumperReceipt:
    lumper_fee: Decimal
    late_fee: Decimal = Decimal("0.00")
    parking_fee: Decimal = Decimal("0.00")
    tip: Decimal = Decimal("0.00")
    receipt_provided: bool = True
    preapproved_over_limit: bool = False


@dataclass(frozen=True)
class ReimbursementTerms:
    no_receipt_limit: Decimal = DEFAULT_NO_RECEIPT_LIMIT
    approval_limit: Decimal = DEFAULT_APPROVAL_LIMIT
    markup_rate: Decimal = DEFAULT_MARKUP_RATE
    pass_through_only: bool = False
    max_customer_bill: Decimal | None = DEFAULT_MAX_CUSTOMER_BILL


@dataclass(frozen=True)
class ReimbursementResult:
    carrier_pay: Decimal
    customer_bill: Decimal
    denied_amount: Decimal


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate(receipt: LumperReceipt, terms: ReimbursementTerms) -> None:
    for name, value in (
        ("lumper_fee", receipt.lumper_fee),
        ("late_fee", receipt.late_fee),
        ("parking_fee", receipt.parking_fee),
        ("tip", receipt.tip),
        ("no_receipt_limit", terms.no_receipt_limit),
        ("approval_limit", terms.approval_limit),
        ("markup_rate", terms.markup_rate),
    ):
        if value < 0:
            raise ValueError(f"{name} cannot be negative: {value}")
    if terms.max_customer_bill is not None and terms.max_customer_bill < 0:
        raise ValueError(f"max_customer_bill cannot be negative: {terms.max_customer_bill}")


def _receipt_total(receipt: LumperReceipt) -> Decimal:
    return _money(receipt.lumper_fee + receipt.late_fee + receipt.parking_fee + receipt.tip)


def _approved_base(receipt: LumperReceipt, terms: ReimbursementTerms) -> Decimal:
    total = _receipt_total(receipt)
    if not receipt.receipt_provided and total > terms.no_receipt_limit + CASH_TOLERANCE:
        return Decimal("0.00")

    base = _money(receipt.lumper_fee)
    if receipt.preapproved_over_limit:
        return base
    if base <= terms.approval_limit + CASH_TOLERANCE:
        return base
    return _money(terms.approval_limit)


def _customer_bill(base: Decimal, terms: ReimbursementTerms) -> Decimal:
    if base == Decimal("0.00"):
        return base
    if terms.pass_through_only:
        billed = base
    else:
        billed = _money(base * (Decimal("1.00") + terms.markup_rate))
    if terms.max_customer_bill is not None and billed > terms.max_customer_bill:
        return terms.max_customer_bill
    return billed


def calculate_lumper_reimbursement(
    receipt: LumperReceipt, terms: ReimbursementTerms = ReimbursementTerms()
) -> ReimbursementResult:
    """Compute carrier reimbursement and customer billing for one lumper receipt.

    Only the lumper service fee is eligible. Late fees, parking and tips are denied.
    If no receipt is provided, reimbursement is allowed only when the full claimed
    receipt total is within the no-receipt limit, allowing up to five cents of cash
    rounding. Without pre-approval, the reimbursable lumper fee is capped at the
    approval limit, again allowing up to five cents over the limit.
    """
    _validate(receipt, terms)
    approved = _approved_base(receipt, terms)
    denied = _money(_receipt_total(receipt) - approved)
    return ReimbursementResult(
        carrier_pay=approved,
        customer_bill=_customer_bill(approved, terms),
        denied_amount=denied,
    )
