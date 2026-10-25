"""Factoring-fee deductions for settled carrier invoices.

The settlement service uses these rules to estimate what a factor will deduct from an
invoice purchase. Only eligible receivable value is subject to the fee and reserve:
linehaul is always eligible, fuel is eligible only when the customer allows assignment,
and accessorials are excluded by default unless marked eligible. A minimum advance of
$250.00 is required for funding; if the computed advance is smaller, nothing is funded
and no fee is deducted. Factoring fees are assessed on the eligible amount after any
same-day submission discount and before reserve is withheld. Reserve is a percentage of
that same discounted eligible amount and is tracked separately from the fee. High-risk
customers incur a 0.50% fee surcharge, while non-recourse programs add 1.00%. Loads on
credit hold are not fundable. Amounts are rounded to the cent using half-up rounding,
and negative money inputs are rejected.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
MIN_ADVANCE = Decimal("250.00")
SAME_DAY_DISCOUNT = Decimal("0.0025")
HIGH_RISK_SURCHARGE = Decimal("0.0050")
NON_RECOURSE_SURCHARGE = Decimal("0.0100")
MAX_FEE_RATE = Decimal("0.0800")


@dataclass(frozen=True)
class ReceivableBreakdown:
    linehaul: Decimal
    fuel_surcharge: Decimal = Decimal("0.00")
    accessorials: Decimal = Decimal("0.00")
    fuel_assignable: bool = True
    accessorials_eligible: bool = False
    same_day_submission: bool = False
    on_credit_hold: bool = False
    high_risk_customer: bool = False


@dataclass(frozen=True)
class FactoringTerms:
    base_fee_rate: Decimal = Decimal("0.0300")
    reserve_rate: Decimal = Decimal("0.1000")
    advance_rate: Decimal = Decimal("0.9000")
    non_recourse: bool = False


@dataclass(frozen=True)
class FactoringDeduction:
    eligible_amount: Decimal
    fee_amount: Decimal
    reserve_amount: Decimal
    advance_amount: Decimal


def _q(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate_money(name: str, amount: Decimal) -> None:
    if amount < Decimal("0.00"):
        raise ValueError(f"{name} cannot be negative: {amount}")


def _validate_terms(terms: FactoringTerms) -> None:
    for name, rate in (
        ("base_fee_rate", terms.base_fee_rate),
        ("reserve_rate", terms.reserve_rate),
        ("advance_rate", terms.advance_rate),
    ):
        if rate < Decimal("0.00") or rate > Decimal("1.00"):
            raise ValueError(f"{name} must be between 0 and 1: {rate}")


def _eligible_amount(receivable: ReceivableBreakdown) -> Decimal:
    eligible = receivable.linehaul
    if receivable.fuel_assignable:
        eligible += receivable.fuel_surcharge
    if receivable.accessorials_eligible:
        eligible += receivable.accessorials
    return eligible


def _effective_fee_rate(receivable: ReceivableBreakdown, terms: FactoringTerms) -> Decimal:
    rate = terms.base_fee_rate
    if receivable.high_risk_customer:
        rate += HIGH_RISK_SURCHARGE
    if terms.non_recourse:
        rate += NON_RECOURSE_SURCHARGE
    if rate > MAX_FEE_RATE:
        rate = MAX_FEE_RATE
    return rate


def calculate_factoring_fee_deduction(
    receivable: ReceivableBreakdown, terms: FactoringTerms = FactoringTerms()
) -> FactoringDeduction:
    """Return estimated fee, reserve, and advance for one receivable purchase."""
    _validate_money("linehaul", receivable.linehaul)
    _validate_money("fuel_surcharge", receivable.fuel_surcharge)
    _validate_money("accessorials", receivable.accessorials)
    _validate_terms(terms)

    if receivable.on_credit_hold:
        return FactoringDeduction(
            eligible_amount=Decimal("0.00"),
            fee_amount=Decimal("0.00"),
            reserve_amount=Decimal("0.00"),
            advance_amount=Decimal("0.00"),
        )

    eligible = _eligible_amount(receivable)
    if eligible == Decimal("0.00"):
        return FactoringDeduction(Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00"))

    discounted = eligible
    if receivable.same_day_submission:
        discounted = eligible * (Decimal("1.00") - SAME_DAY_DISCOUNT)

    discounted = _q(discounted)
    fee_amount = _q(discounted * _effective_fee_rate(receivable, terms))
    reserve_amount = _q(discounted * terms.reserve_rate)
    advance_amount = _q(discounted * terms.advance_rate - fee_amount)

    if advance_amount < MIN_ADVANCE:
        return FactoringDeduction(
            eligible_amount=discounted,
            fee_amount=Decimal("0.00"),
            reserve_amount=Decimal("0.00"),
            advance_amount=Decimal("0.00"),
        )

    return FactoringDeduction(
        eligible_amount=discounted,
        fee_amount=fee_amount,
        reserve_amount=reserve_amount,
        advance_amount=advance_amount,
    )
