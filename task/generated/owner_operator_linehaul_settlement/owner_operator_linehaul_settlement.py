"""Owner-operator linehaul settlement for one load.

Tidewater settles owner-operators on gross linehaul revenue after contract pay is
computed and only authorized settlement deductions are taken. This module covers the
common one-load case with these rules:

* Compensation is either a percent of gross linehaul or a flat amount per loaded mile.
* Gross linehaul below zero is invalid. Loaded miles may be zero but not negative.
* Percentage contracts pay gross multiplied by the contract percent, rounded half up to
  the cent. Mileage contracts pay loaded miles times the per-mile rate, rounded half up.
* Fuel surcharge, accessorials and pass-through charges are not inputs here; only gross
  linehaul and the contract basis are settled.
* Deductions are applied only when individually authorized. Negative deductions are
  rejected. A non-authorized deduction is ignored rather than settled.
* Escrow is deducted only until the driver's escrow balance reaches the target. The
  deduction is the lesser of the requested amount and the remaining amount to target.
* Occupational accident is deducted only when enrolled. If not enrolled, that deduction
  line is ignored.
* Net settlement cannot go below a holdback floor. If deductions would push net below
  the floor, deductions are reduced so final net equals the floor.
* A settlement cap may limit gross pay before deductions. A guaranteed minimum may raise
  gross pay before deductions. The minimum is applied first, then the cap.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


@dataclass(frozen=True)
class PayBasis:
    percent_of_linehaul: Decimal | None = None
    rate_per_loaded_mile: Decimal | None = None


@dataclass(frozen=True)
class SettlementDeductions:
    escrow_request: Decimal = Decimal("0.00")
    escrow_balance: Decimal = Decimal("0.00")
    escrow_target: Decimal = Decimal("0.00")
    occupational_accident: Decimal = Decimal("0.00")
    occ_acc_enrolled: bool = False
    device_rental: Decimal = Decimal("0.00")
    device_rental_authorized: bool = False
    chargeback: Decimal = Decimal("0.00")
    chargeback_authorized: bool = False


@dataclass(frozen=True)
class SettlementTerms:
    guaranteed_minimum_gross: Decimal = Decimal("0.00")
    gross_pay_cap: Decimal | None = None
    net_floor: Decimal = Decimal("0.00")


def _money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate(gross_linehaul: Decimal, loaded_miles: int, basis: PayBasis, deductions: SettlementDeductions, terms: SettlementTerms) -> None:
    if gross_linehaul < 0:
        raise ValueError("gross_linehaul cannot be negative")
    if loaded_miles < 0:
        raise ValueError("loaded_miles cannot be negative")
    if (basis.percent_of_linehaul is None) == (basis.rate_per_loaded_mile is None):
        raise ValueError("exactly one pay basis must be set")
    if basis.percent_of_linehaul is not None and not (Decimal("0") <= basis.percent_of_linehaul <= Decimal("1")):
        raise ValueError("percent_of_linehaul must be between 0 and 1")
    for amount in (
        basis.rate_per_loaded_mile,
        deductions.escrow_request,
        deductions.escrow_balance,
        deductions.escrow_target,
        deductions.occupational_accident,
        deductions.device_rental,
        deductions.chargeback,
        terms.guaranteed_minimum_gross,
        terms.net_floor,
    ):
        if amount is not None and amount < 0:
            raise ValueError("amounts cannot be negative")
    if terms.gross_pay_cap is not None and terms.gross_pay_cap < 0:
        raise ValueError("gross_pay_cap cannot be negative")


def _base_gross_pay(gross_linehaul: Decimal, loaded_miles: int, basis: PayBasis) -> Decimal:
    if basis.percent_of_linehaul is not None:
        return _money(gross_linehaul * basis.percent_of_linehaul)
    return _money(Decimal(loaded_miles) * basis.rate_per_loaded_mile)


def _apply_minimum_and_cap(gross_pay: Decimal, terms: SettlementTerms) -> Decimal:
    adjusted = max(gross_pay, terms.guaranteed_minimum_gross)
    if terms.gross_pay_cap is not None:
        adjusted = min(adjusted, terms.gross_pay_cap)
    return _money(adjusted)


def _allowed_deductions(deductions: SettlementDeductions) -> Decimal:
    total = Decimal("0.00")
    remaining_escrow = max(Decimal("0.00"), deductions.escrow_target - deductions.escrow_balance)
    total += min(deductions.escrow_request, remaining_escrow)
    if deductions.occ_acc_enrolled:
        total += deductions.occupational_accident
    if deductions.device_rental_authorized:
        total += deductions.device_rental
    if deductions.chargeback_authorized:
        total += deductions.chargeback
    return _money(total)


def calculate_owner_operator_linehaul_settlement(
    gross_linehaul: Decimal,
    loaded_miles: int,
    pay_basis: PayBasis,
    deductions: SettlementDeductions = SettlementDeductions(),
    terms: SettlementTerms = SettlementTerms(),
) -> Decimal:
    """Return the net owner-operator linehaul settlement for one load.

    Net settlement is contract gross pay, adjusted by any guaranteed minimum and gross
    pay cap, less allowed deductions, but never below ``terms.net_floor``.
    """
    _validate(gross_linehaul, loaded_miles, pay_basis, deductions, terms)
    gross_pay = _apply_minimum_and_cap(_base_gross_pay(gross_linehaul, loaded_miles, pay_basis), terms)
    deduction_total = _allowed_deductions(deductions)
    net = gross_pay - deduction_total
    if net < terms.net_floor:
        net = terms.net_floor
    return _money(net)
