"""Owner-operator settlement for billed accessorials.

This module converts one billed accessorial on a customer load into the payable amount
for the owner-operator. The settlement team uses these rules when a billed charge is
shared with the truck under the contractor schedule.

Business rules:
- Negative billed amounts are not allowed.
- Some items are pure pass-through reimbursements and pay 100% of the billed amount.
- Fuel surcharge never pays as an accessorial settlement item.
- Lumper reimbursement pays 100% only when a receipt is on file; otherwise it pays 0%.
- Detention pays the configured percentage, but only when billed amount is at least the
  contractual minimum approval threshold.
- TONU pays the configured percentage, but if the truck was not on time for pickup it
  pays 0%.
- Layover pays the configured percentage, but owner-operators do not participate in the
  first 150.00 billed dollars; only the excess is shareable.
- Driver assist pays the configured percentage, but is capped at 250.00 payable.
- Unknown item codes use the default percentage.
- After all item rules, if the owner-operator is in the grace period and the payable
  amount is below 25.00, the settlement is rounded down to 0.00 to avoid nuisance pay.
- Currency is rounded to the nearest cent using half-up rounding.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
LAYOVER_DEDUCTIBLE = Decimal("150.00")
SMALL_PAY_FLOOR = Decimal("25.00")
DEFAULT_MIN_DETENTION = Decimal("50.00")
DEFAULT_DRIVER_ASSIST_CAP = Decimal("250.00")


@dataclass(frozen=True)
class AccessorialItem:
    code: str
    billed_amount: Decimal
    has_receipt: bool = False
    truck_on_time: bool = True


@dataclass(frozen=True)
class SettlementTerms:
    default_percentage: Decimal = Decimal("0.65")
    detention_percentage: Decimal = Decimal("0.70")
    tonu_percentage: Decimal = Decimal("0.75")
    layover_percentage: Decimal = Decimal("0.60")
    driver_assist_percentage: Decimal = Decimal("0.50")
    min_detention_billed: Decimal = DEFAULT_MIN_DETENTION
    driver_assist_cap: Decimal = DEFAULT_DRIVER_ASSIST_CAP
    in_grace_period: bool = False


def _normalize_code(code: str) -> str:
    return code.strip().upper().replace("-", "_").replace(" ", "_")


def _round_money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate(item: AccessorialItem, terms: SettlementTerms) -> None:
    if item.billed_amount < Decimal("0.00"):
        raise ValueError("billed_amount cannot be negative")
    percentages = (
        terms.default_percentage,
        terms.detention_percentage,
        terms.tonu_percentage,
        terms.layover_percentage,
        terms.driver_assist_percentage,
    )
    for pct in percentages:
        if pct < Decimal("0.00") or pct > Decimal("1.00"):
            raise ValueError("percentages must be between 0.00 and 1.00")
    if terms.min_detention_billed < Decimal("0.00"):
        raise ValueError("min_detention_billed cannot be negative")
    if terms.driver_assist_cap < Decimal("0.00"):
        raise ValueError("driver_assist_cap cannot be negative")


def _percentage_pay(amount: Decimal, pct: Decimal) -> Decimal:
    return _round_money(amount * pct)


def calculate_owner_operator_accessorial_settlement(
    item: AccessorialItem, terms: SettlementTerms = SettlementTerms()
) -> Decimal:
    """Return owner-operator payable for one billed accessorial line.

    >>> calculate_owner_operator_accessorial_settlement(
    ...     AccessorialItem(code="detention", billed_amount=Decimal("100.00"))
    ... )
    Decimal('70.00')
    """
    _validate(item, terms)
    code = _normalize_code(item.code)
    billed = _round_money(item.billed_amount)

    if billed == Decimal("0.00"):
        return billed
    if code in {"FUEL", "FUEL_SURCHARGE", "FSC"}:
        payable = Decimal("0.00")
    elif code in {"LUMPER", "LUMPER_REIMBURSEMENT"}:
        payable = billed if item.has_receipt else Decimal("0.00")
    elif code == "DETENTION":
        payable = (
            Decimal("0.00")
            if billed < terms.min_detention_billed
            else _percentage_pay(billed, terms.detention_percentage)
        )
    elif code in {"TONU", "TRUCK_ORDERED_NOT_USED"}:
        payable = (
            Decimal("0.00")
            if not item.truck_on_time
            else _percentage_pay(billed, terms.tonu_percentage)
        )
    elif code == "LAYOVER":
        shareable = billed - LAYOVER_DEDUCTIBLE
        payable = (
            Decimal("0.00")
            if shareable <= Decimal("0.00")
            else _percentage_pay(shareable, terms.layover_percentage)
        )
    elif code in {"DRIVER_ASSIST", "DRIVERASSIST"}:
        payable = _percentage_pay(billed, terms.driver_assist_percentage)
        if payable > terms.driver_assist_cap:
            payable = terms.driver_assist_cap
    else:
        payable = _percentage_pay(billed, terms.default_percentage)

    if terms.in_grace_period and payable < SMALL_PAY_FLOOR:
        return Decimal("0.00")
    return _round_money(payable)
