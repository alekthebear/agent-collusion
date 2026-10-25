"""Net settlement fee offsets between a carrier and Tidewater entities.

During settlement, we may offset what we owe a carrier against what the carrier owes
us, but only for balances that are legally nettable and still collectible under our
aging policy. Netting is done per legal entity: a receivable on one Tidewater entity
cannot offset a payable owed by another entity.

Business rules implemented here:
- Receivables are eligible only when ``approved`` is true, ``disputed`` is false, and
  ``days_past_due`` is between 0 and 120 inclusive.
- A receivable with a credit hold is still nettable, but only at 50% of its face
  amount to reflect collection risk.
- Tiny receivables under $5.00 are ignored because we do not net nuisance balances.
- Payables are eligible only when ``ready_to_pay`` is true and ``days_old`` is between
  0 and 45 inclusive.
- If the payable is marked ``expedite_requested``, a 1.5% fee applies to the amount
  actually netted, with a minimum fee of $2.00 and a maximum of $25.00.
- No expedite fee is charged when nothing can be netted.
- All currency results are rounded half up to the cent.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
MIN_RECEIVABLE = Decimal("5.00")
CREDIT_HOLD_FACTOR = Decimal("0.50")
EXPEDITE_RATE = Decimal("0.015")
EXPEDITE_MIN = Decimal("2.00")
EXPEDITE_MAX = Decimal("25.00")


@dataclass(frozen=True)
class ReceivableBalance:
    entity_code: str
    amount: Decimal
    days_past_due: int
    approved: bool = True
    disputed: bool = False
    credit_hold: bool = False


@dataclass(frozen=True)
class PayableBalance:
    entity_code: str
    amount: Decimal
    days_old: int
    ready_to_pay: bool = True
    expedite_requested: bool = False


@dataclass(frozen=True)
class SettlementFeeNetting:
    netted_amount: Decimal
    expedite_fee: Decimal
    net_payable: Decimal


def _q(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate_receivable(item: ReceivableBalance) -> None:
    if item.amount < Decimal("0.00"):
        raise ValueError("receivable amount cannot be negative")


def _validate_payable(item: PayableBalance) -> None:
    if item.amount < Decimal("0.00"):
        raise ValueError("payable amount cannot be negative")


def _eligible_receivable_amount(item: ReceivableBalance, entity_code: str) -> Decimal:
    if item.entity_code != entity_code:
        return Decimal("0.00")
    if not item.approved or item.disputed:
        return Decimal("0.00")
    if item.days_past_due < 0 or item.days_past_due > 120:
        return Decimal("0.00")
    if item.amount < MIN_RECEIVABLE:
        return Decimal("0.00")
    amount = item.amount * (CREDIT_HOLD_FACTOR if item.credit_hold else Decimal("1.00"))
    return _q(amount)


def _payable_is_eligible(item: PayableBalance, entity_code: str) -> bool:
    return (
        item.entity_code == entity_code
        and item.ready_to_pay
        and 0 <= item.days_old <= 45
    )


def _expedite_fee(netted_amount: Decimal, expedite_requested: bool) -> Decimal:
    if not expedite_requested or netted_amount == Decimal("0.00"):
        return Decimal("0.00")
    fee = _q(netted_amount * EXPEDITE_RATE)
    if fee < EXPEDITE_MIN:
        return EXPEDITE_MIN
    if fee > EXPEDITE_MAX:
        return EXPEDITE_MAX
    return fee


def calculate_settlement_fee_netting(
    payable: PayableBalance,
    receivables: list[ReceivableBalance],
) -> SettlementFeeNetting:
    """Compute the payable left after legal-entity netting and any expedite fee.

    The payable is reduced by the sum of eligible receivables for the same entity,
    limited so the payable never goes below zero. If the payable is eligible and marked
    for expedition, a fee is charged on the amount actually netted.
    """
    _validate_payable(payable)
    for item in receivables:
        _validate_receivable(item)

    if not _payable_is_eligible(payable, payable.entity_code):
        return SettlementFeeNetting(
            netted_amount=Decimal("0.00"),
            expedite_fee=Decimal("0.00"),
            net_payable=_q(payable.amount),
        )

    eligible_total = sum(
        (_eligible_receivable_amount(item, payable.entity_code) for item in receivables),
        start=Decimal("0.00"),
    )
    netted = min(_q(payable.amount), _q(eligible_total))
    fee = _expedite_fee(netted, payable.expedite_requested)
    net_payable = _q(payable.amount - netted + fee)
    return SettlementFeeNetting(netted_amount=netted, expedite_fee=fee, net_payable=net_payable)
