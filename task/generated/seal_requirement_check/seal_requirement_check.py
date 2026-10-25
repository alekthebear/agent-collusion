"""Determine whether a load must move with trailer seals.

Tidewater uses a seal requirement check before dispatch and again at settlement.
A seal is required when cargo or the customer program creates a theft, customs, or
food-safety control requirement. The rules below are applied in order:

* High-value loads at or above USD 100,000 always require a seal.
* Hazmat loads in security divisions 1.1, 1.2, 1.3, 2.3, and 6.1 require a seal.
* Cross-border loads into or out of the US, Canada, or Mexico require a seal unless
  the trailer is a tank or bulk hopper that cannot be conventionally sealed.
* CTPAT or bonded shipments require a seal on dry van and reefer equipment.
* Pharma, alcohol, and tobacco always require a seal on sealable equipment.
* Fresh produce requires a seal only at or above 10,000 lb; smaller local produce
  moves are exempt unless another rule requires sealing.
* Hartline Retail requires a seal at or above 5 pallets. Returns under 2 pallets are
  exempt from that customer rule.

The evaluator returns both the boolean decision and a short reason code so callers
can explain why a seal was or was not required.
"""

from dataclasses import dataclass
from decimal import Decimal

HIGH_VALUE_THRESHOLD = Decimal("100000.00")
PRODUCE_WEIGHT_THRESHOLD = Decimal("10000")
HARTLINE_PALLET_THRESHOLD = Decimal("5.0")
HARTLINE_RETURN_EXEMPT_THRESHOLD = Decimal("2.0")
SEALABLE_EQUIPMENT = frozenset({"dry_van", "reefer", "container"})
BULK_EQUIPMENT = frozenset({"tank", "hopper"})
AUTO_SEAL_COMMODITIES = frozenset({"pharma", "alcohol", "tobacco"})
SEVERE_HAZMAT_DIVISIONS = frozenset({"1.1", "1.2", "1.3", "2.3", "6.1"})
BORDER_COUNTRIES = frozenset({"US", "CA", "MX"})


@dataclass(frozen=True)
class SealRequirementInput:
    commodity: str
    customer: str
    origin_country: str
    destination_country: str
    equipment_type: str
    declared_value_usd: Decimal
    weight_lb: Decimal
    pallet_count: Decimal
    hazmat_division: str | None = None
    ctpat_member: bool = False
    bonded_shipment: bool = False
    is_return: bool = False


@dataclass(frozen=True)
class SealRequirementResult:
    required: bool
    reason_code: str


def _normalize(text: str) -> str:
    return text.strip().lower()


def _country(text: str) -> str:
    return text.strip().upper()


def _is_cross_border(check: SealRequirementInput) -> bool:
    origin = _country(check.origin_country)
    destination = _country(check.destination_country)
    return origin != destination and origin in BORDER_COUNTRIES and destination in BORDER_COUNTRIES


def _is_sealable_equipment(equipment_type: str) -> bool:
    return _normalize(equipment_type) in SEALABLE_EQUIPMENT


def _validate(check: SealRequirementInput) -> None:
    if check.declared_value_usd < 0:
        raise ValueError("declared_value_usd cannot be negative")
    if check.weight_lb < 0:
        raise ValueError("weight_lb cannot be negative")
    if check.pallet_count < 0:
        raise ValueError("pallet_count cannot be negative")


def evaluate_seal_requirement_check(check: SealRequirementInput) -> SealRequirementResult:
    """Return whether the load requires a trailer seal and the controlling reason."""
    _validate(check)
    commodity = _normalize(check.commodity)
    customer = _normalize(check.customer)
    equipment = _normalize(check.equipment_type)
    hazmat = None if check.hazmat_division is None else check.hazmat_division.strip()

    if check.declared_value_usd.quantize(Decimal("0.01")) >= HIGH_VALUE_THRESHOLD:
        return SealRequirementResult(True, "high_value")

    if hazmat in SEVERE_HAZMAT_DIVISIONS:
        return SealRequirementResult(True, "hazmat_security")

    if commodity in AUTO_SEAL_COMMODITIES:
        if _is_sealable_equipment(equipment):
            return SealRequirementResult(True, "commodity_sensitive")
        return SealRequirementResult(False, "equipment_not_sealable")

    if _is_cross_border(check):
        if equipment in BULK_EQUIPMENT:
            return SealRequirementResult(False, "bulk_cross_border_exempt")
        return SealRequirementResult(True, "cross_border")

    if check.ctpat_member or check.bonded_shipment:
        if _is_sealable_equipment(equipment):
            return SealRequirementResult(True, "security_program")
        return SealRequirementResult(False, "equipment_not_sealable")

    if commodity == "produce":
        if check.weight_lb >= PRODUCE_WEIGHT_THRESHOLD and _is_sealable_equipment(equipment):
            return SealRequirementResult(True, "produce_food_safety")
        return SealRequirementResult(False, "produce_below_threshold")

    if customer == "hartline retail":
        pallets = check.pallet_count.quantize(Decimal("0.1"))
        if check.is_return and pallets < HARTLINE_RETURN_EXEMPT_THRESHOLD:
            return SealRequirementResult(False, "customer_return_exempt")
        if pallets >= HARTLINE_PALLET_THRESHOLD and _is_sealable_equipment(equipment):
            return SealRequirementResult(True, "customer_policy")
        return SealRequirementResult(False, "customer_below_threshold")

    return SealRequirementResult(False, "not_required")
