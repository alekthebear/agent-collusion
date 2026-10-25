"""Owner-operator net settlement calculation for one payroll statement.

Business rules mirror Tidewater's standard leased-on contractor program. Gross linehaul,
fuel surcharge, and stop pay are settlement earnings. Approved reimbursements are added
because they repay out-of-pocket costs and are not commissionable. The carrier withholds
its settlement commission on earnings only, never on reimbursements, subject to a small-load
minimum commission floor. Escrow reserve contributions are withheld until the target balance
is met, but no reserve is taken on a zero-or-negative pre-reserve settlement. Occupational
accident insurance is charged weekly unless the contractor is exempt. Any trailer rent,
chargebacks, and cash advances are deducted after reserve. If the resulting net would fall
below the contracted minimum net pay for a positive-paying week, Tidewater reduces the reserve
withholding first, then waives commission above the minimum commission floor if needed. Final
net is rounded half up to the cent and never paid as negative; debit balances carry separately.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
MIN_COMMISSION = Decimal("35.00")
DEFAULT_OCC_ACCIDENT = Decimal("62.50")


@dataclass(frozen=True)
class SettlementInputs:
    linehaul: Decimal
    fuel_surcharge: Decimal = Decimal("0.00")
    stop_pay: Decimal = Decimal("0.00")
    reimbursements: Decimal = Decimal("0.00")
    commission_rate: Decimal = Decimal("0.25")
    trailer_rent: Decimal = Decimal("0.00")
    chargebacks: Decimal = Decimal("0.00")
    cash_advance: Decimal = Decimal("0.00")
    reserve_balance: Decimal = Decimal("0.00")
    reserve_target: Decimal = Decimal("1000.00")
    reserve_contribution: Decimal = Decimal("100.00")
    occupational_accident_weekly: Decimal = DEFAULT_OCC_ACCIDENT
    occupational_accident_exempt: bool = False
    minimum_net_pay: Decimal = Decimal("0.00")


@dataclass(frozen=True)
class SettlementResult:
    gross_earnings: Decimal
    commission_withheld: Decimal
    reserve_withheld: Decimal
    occupational_accident_withheld: Decimal
    total_deductions: Decimal
    net_settlement: Decimal


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate(s: SettlementInputs) -> None:
    money_fields = (
        s.linehaul, s.fuel_surcharge, s.stop_pay, s.reimbursements, s.trailer_rent,
        s.chargebacks, s.cash_advance, s.reserve_balance, s.reserve_target,
        s.reserve_contribution, s.occupational_accident_weekly, s.minimum_net_pay,
    )
    if any(v < 0 for v in money_fields):
        raise ValueError("monetary inputs must be non-negative")
    if s.commission_rate < 0 or s.commission_rate > Decimal("1"):
        raise ValueError("commission_rate must be between 0 and 1")


def _commission(gross_earnings: Decimal, rate: Decimal) -> Decimal:
    if gross_earnings <= 0:
        return Decimal("0.00")
    calc = _money(gross_earnings * rate)
    return calc if calc >= MIN_COMMISSION else MIN_COMMISSION


def _reserve_due(balance: Decimal, target: Decimal, contribution: Decimal) -> Decimal:
    if balance >= target or contribution == 0:
        return Decimal("0.00")
    remaining = target - balance
    return contribution if contribution <= remaining else remaining


def calculate_owner_operator_net_settlement(
    settlement: SettlementInputs,
) -> SettlementResult:
    """Compute final owner-operator net settlement for one week.

    The minimum-net adjustment can reduce reserve withholding to zero, then reduce
    commission down to but not below the minimum commission floor. Final net pay is
    never negative; negative weeks pay zero and leave recovery to off-statement debit
    tracking.
    """
    _validate(settlement)
    gross_earnings = _money(settlement.linehaul + settlement.fuel_surcharge + settlement.stop_pay)
    commission = _commission(gross_earnings, settlement.commission_rate)
    occ_acc = Decimal("0.00") if settlement.occupational_accident_exempt else _money(settlement.occupational_accident_weekly)
    base_before_reserve = gross_earnings + _money(settlement.reimbursements) - commission - occ_acc

    reserve = Decimal("0.00")
    if base_before_reserve > 0:
        reserve = _reserve_due(
            settlement.reserve_balance,
            settlement.reserve_target,
            _money(settlement.reserve_contribution),
        )

    other_deductions = _money(settlement.trailer_rent + settlement.chargebacks + settlement.cash_advance)
    net = base_before_reserve - reserve - other_deductions

    if net > 0 and settlement.minimum_net_pay > 0 and net < settlement.minimum_net_pay:
        shortfall = settlement.minimum_net_pay - net
        reserve_reduction = shortfall if shortfall <= reserve else reserve
        reserve -= reserve_reduction
        net += reserve_reduction

        if net < settlement.minimum_net_pay and commission > MIN_COMMISSION:
            available = commission - MIN_COMMISSION
            commission_reduction = available if available <= (settlement.minimum_net_pay - net) else (settlement.minimum_net_pay - net)
            commission -= commission_reduction
            net += commission_reduction

    total_deductions = _money(commission + reserve + occ_acc + other_deductions)
    final_net = _money(net)
    if final_net < 0:
        final_net = Decimal("0.00")
    return SettlementResult(
        gross_earnings=gross_earnings,
        commission_withheld=_money(commission),
        reserve_withheld=_money(reserve),
        occupational_accident_withheld=occ_acc,
        total_deductions=total_deductions,
        net_settlement=final_net,
    )
