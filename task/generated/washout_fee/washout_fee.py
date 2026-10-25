"""Trailer washout reimbursement for contaminated equipment after delivery.

A washout is reimbursable only when the delivered commodity leaves the trailer needing
cleaning for the next load. The settlement service uses the rules below to decide how
much of a carrier-submitted wash receipt may be passed through to the customer.

Business rules:
- The required wash level is driven by the stronger of the commodity contamination
  class and the next-load requirement supplied by operations.
- Wash levels bill at contract maximums: rinse, standard, sanitize, and hazmat.
- Contracts may disallow pass-through entirely, or may disallow premium hazmat
  reimbursement even when a hazmat wash was operationally required.
- The reimbursable amount is the lesser of the actual receipt and the allowed maximum,
  reduced by any carrier deductible, then rounded to cents.
- Receipts at or below the deductible reimburse zero. Negative receipts and invalid
  combinations are rejected.
- Food-grade commodities require at least a sanitize wash.
- Non-contaminating dry freight does not reimburse unless operations explicitly require
  a wash for the next load.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")

_LEVEL_ORDER = {"none": 0, "rinse": 1, "standard": 2, "sanitize": 3, "hazmat": 4}
_CLASS_MINIMUM = {
    "dry": "none",
    "produce": "rinse",
    "food": "sanitize",
    "chemical": "standard",
    "hazmat": "hazmat",
}
_MAX_BY_LEVEL = {
    "none": Decimal("0.00"),
    "rinse": Decimal("35.00"),
    "standard": Decimal("85.00"),
    "sanitize": Decimal("140.00"),
    "hazmat": Decimal("225.00"),
}


@dataclass(frozen=True)
class WashoutRequest:
    commodity_class: str
    required_wash_level: str
    receipt_amount: Decimal
    food_grade_trailer: bool = False


@dataclass(frozen=True)
class PassThroughTerms:
    allow_pass_through: bool = True
    allow_hazmat_premium: bool = True
    carrier_deductible: Decimal = Decimal("15.00")
    customer_cap: Decimal | None = None


def _validate(request: WashoutRequest, terms: PassThroughTerms) -> None:
    if request.commodity_class not in _CLASS_MINIMUM:
        raise ValueError(f"unknown commodity_class: {request.commodity_class}")
    if request.required_wash_level not in _LEVEL_ORDER:
        raise ValueError(f"unknown required_wash_level: {request.required_wash_level}")
    if request.receipt_amount < 0:
        raise ValueError("receipt_amount cannot be negative")
    if terms.carrier_deductible < 0:
        raise ValueError("carrier_deductible cannot be negative")
    if terms.customer_cap is not None and terms.customer_cap < 0:
        raise ValueError("customer_cap cannot be negative")


def _stronger_level(left: str, right: str) -> str:
    return left if _LEVEL_ORDER[left] >= _LEVEL_ORDER[right] else right


def _required_level(request: WashoutRequest) -> str:
    level = _stronger_level(_CLASS_MINIMUM[request.commodity_class], request.required_wash_level)
    if request.food_grade_trailer and _LEVEL_ORDER[level] < _LEVEL_ORDER["sanitize"]:
        return "sanitize"
    return level


def _allowed_maximum(level: str, terms: PassThroughTerms) -> Decimal:
    if not terms.allow_pass_through:
        return Decimal("0.00")
    if level == "hazmat" and not terms.allow_hazmat_premium:
        return _MAX_BY_LEVEL["standard"]
    return _MAX_BY_LEVEL[level]


def _apply_cap(amount: Decimal, cap: Decimal | None) -> Decimal:
    if cap is not None and amount > cap:
        return cap
    return amount


def calculate_washout_fee(
    request: WashoutRequest, terms: PassThroughTerms = PassThroughTerms()
) -> Decimal:
    """Reimbursable washout amount in dollars, rounded to the cent.

    The payable amount is limited by the required wash level, contract settings,
    optional customer cap, and the carrier deductible.
    """
    _validate(request, terms)
    level = _required_level(request)
    if level == "none":
        return Decimal("0.00")

    allowed = _allowed_maximum(level, terms)
    allowed = _apply_cap(allowed, terms.customer_cap)
    eligible = min(request.receipt_amount, allowed)
    if eligible <= terms.carrier_deductible:
        return Decimal("0.00")

    reimbursable = eligible - terms.carrier_deductible
    return reimbursable.quantize(CENT, rounding=ROUND_HALF_UP)
