"""Cash advance setoff rules used during driver settlement.

A prior cash advance is recovered from a settlement by applying a repayment rate to
linehaul compensation, then enforcing safety rails common in fleet agreements.
Standard terms are: advances under $25 are not set off, 35% of linehaul is the base
recovery, settlements with linehaul under $150 are protected from any deduction,
and the driver's net pay after setoff must stay at or above a minimum protected
amount. Fuel reimbursement and lumper reimbursement are never used to increase the
setoff base, but they do count toward net pay available to protect the minimum.
The final setoff can never exceed the outstanding advance balance or the settlement's
payable amount, and is rounded half up to the cent.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
MIN_ADVANCE_TO_COLLECT = Decimal("25.00")
DEFAULT_REPAYMENT_RATE = Decimal("0.35")
DEFAULT_MIN_LINEHAUL_FOR_SET_OFF = Decimal("150.00")
DEFAULT_MIN_NET_PAY = Decimal("100.00")


@dataclass(frozen=True)
class SettlementAmounts:
    """Pay components for one settlement statement."""

    linehaul: Decimal
    fuel_reimbursement: Decimal = Decimal("0.00")
    lumper_reimbursement: Decimal = Decimal("0.00")
    other_deductions: Decimal = Decimal("0.00")


@dataclass(frozen=True)
class SetoffTerms:
    repayment_rate: Decimal = DEFAULT_REPAYMENT_RATE
    min_linehaul_for_setoff: Decimal = DEFAULT_MIN_LINEHAUL_FOR_SET_OFF
    min_net_pay: Decimal = DEFAULT_MIN_NET_PAY
    min_advance_to_collect: Decimal = MIN_ADVANCE_TO_COLLECT


@dataclass(frozen=True)
class CashAdvanceStatus:
    """Outstanding prior advance balance to recover."""

    outstanding_balance: Decimal


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate(amounts: SettlementAmounts, status: CashAdvanceStatus, terms: SetoffTerms) -> None:
    if amounts.linehaul < 0 or amounts.fuel_reimbursement < 0 or amounts.lumper_reimbursement < 0:
        raise ValueError("pay components cannot be negative")
    if amounts.other_deductions < 0:
        raise ValueError("other_deductions cannot be negative")
    if status.outstanding_balance < 0:
        raise ValueError("outstanding_balance cannot be negative")
    if not (Decimal("0") <= terms.repayment_rate <= Decimal("1")):
        raise ValueError("repayment_rate must be between 0 and 1")
    if terms.min_linehaul_for_setoff < 0 or terms.min_net_pay < 0 or terms.min_advance_to_collect < 0:
        raise ValueError("thresholds cannot be negative")


def _gross_pay(amounts: SettlementAmounts) -> Decimal:
    return amounts.linehaul + amounts.fuel_reimbursement + amounts.lumper_reimbursement


def _payable_before_setoff(amounts: SettlementAmounts) -> Decimal:
    payable = _gross_pay(amounts) - amounts.other_deductions
    return payable if payable > Decimal("0.00") else Decimal("0.00")


def _protected_by_min_net_pay(payable_before_setoff: Decimal, min_net_pay: Decimal) -> Decimal:
    protected = payable_before_setoff - min_net_pay
    return protected if protected > Decimal("0.00") else Decimal("0.00")


def calculate_cash_advance_setoff(
    amounts: SettlementAmounts,
    status: CashAdvanceStatus,
    terms: SetoffTerms = SetoffTerms(),
) -> Decimal:
    """Cash advance deduction to take on this settlement.

    Setoff starts from ``repayment_rate * linehaul`` only. No setoff is taken when the
    outstanding balance is below the collectible minimum, when linehaul is below the
    minimum linehaul threshold, or when nothing is payable after other deductions.
    The result is limited by minimum net-pay protection, the outstanding balance, and
    the payable amount, then rounded half up to cents.
    """
    _validate(amounts, status, terms)
    balance = _money(status.outstanding_balance)
    if balance < terms.min_advance_to_collect:
        return Decimal("0.00")
    if amounts.linehaul < terms.min_linehaul_for_setoff:
        return Decimal("0.00")

    payable = _money(_payable_before_setoff(amounts))
    if payable == Decimal("0.00"):
        return Decimal("0.00")

    base_setoff = _money(amounts.linehaul * terms.repayment_rate)
    if base_setoff == Decimal("0.00"):
        return Decimal("0.00")

    max_by_net_pay = _money(_protected_by_min_net_pay(payable, terms.min_net_pay))
    setoff = min(base_setoff, balance, payable, max_by_net_pay)
    if setoff <= Decimal("0.00"):
        return Decimal("0.00")
    return _money(setoff)
