"""Normalize EDI quantities into Tidewater's canonical internal units.

Inbound EDI feeds use several unit codes for weights and dimensions. Billing,
planning, and rating want a single canonical unit per measure, but partners do
not always follow the same conventions across transactions. The rules below are
used during ingest:

- Weight canonical unit is pounds (LB). Kilograms convert at 2.20462 lb/kg.
- Dimension canonical unit is inches (IN). Feet convert at 12 in/ft; meters
  convert at 39.3701 in/m; centimeters convert at 0.393701 in/cm.
- Piece-like counts (EA, CT, PLT) remain counts and are rounded to whole units.
- Transaction-specific overrides apply before conversion. On shipment-status
  transactions (214), partner code ``M`` means minutes, not meters, so it is not
  normalized here. On invoice transactions (210), code ``PC`` means pieces.
- Very small positive weights under 1 lb round up to 1 lb because linehaul and
  accessorial rating do not allow a zero actual weight. Weight over 48,000 lb is
  rejected as an implausible single-line shipment value.
- Dimensions are rounded to the nearest whole inch, except values under 1 inch
  but above zero round up to 1 inch. Dimensions over 1,080 inches are rejected.
- Counts are rounded half up to whole units, but any positive count below 1
  becomes 1. Negative quantities and unknown codes are rejected.
"""

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
KG_TO_LB = Decimal("2.20462")
M_TO_IN = Decimal("39.3701")
CM_TO_IN = Decimal("0.393701")
FT_TO_IN = Decimal("12")
MAX_WEIGHT_LB = Decimal("48000")
MAX_DIMENSION_IN = Decimal("1080")


@dataclass(frozen=True)
class EDIQuantity:
    quantity: Decimal
    unit_code: str
    transaction_set: str
    partner_id: str | None = None


@dataclass(frozen=True)
class NormalizedUnits:
    quantity: Decimal
    canonical_unit: str


def _clean_code(unit_code: str) -> str:
    code = unit_code.strip().upper()
    if not code:
        raise ValueError("unit_code is blank")
    return code


def _effective_code(item: EDIQuantity) -> str:
    code = _clean_code(item.unit_code)
    tx = item.transaction_set.strip()
    if tx == "214" and code == "M":
        raise ValueError("214 transaction uses M for minutes, not a convertible dimension")
    if tx == "210" and code == "PC":
        return "EA"
    return code


def _round_whole_positive(value: Decimal) -> Decimal:
    if value <= 0:
        return Decimal("0")
    if value < 1:
        return Decimal("1")
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _normalize_weight(value: Decimal, factor: Decimal) -> NormalizedUnits:
    pounds = (value * factor).quantize(CENT, rounding=ROUND_HALF_UP)
    if pounds > 0 and pounds < 1:
        pounds = Decimal("1")
    if pounds > MAX_WEIGHT_LB:
        raise ValueError(f"weight {pounds} exceeds {MAX_WEIGHT_LB} lb")
    return NormalizedUnits(quantity=pounds, canonical_unit="LB")


def _normalize_dimension(value: Decimal, factor: Decimal) -> NormalizedUnits:
    inches = value * factor
    if inches > 0 and inches < 1:
        rounded = Decimal("1")
    else:
        rounded = inches.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if rounded > MAX_DIMENSION_IN:
        raise ValueError(f"dimension {rounded} exceeds {MAX_DIMENSION_IN} in")
    return NormalizedUnits(quantity=rounded, canonical_unit="IN")


def _normalize_count(value: Decimal) -> NormalizedUnits:
    return NormalizedUnits(quantity=_round_whole_positive(value), canonical_unit="EA")


def normalize_edi_units(item: EDIQuantity) -> NormalizedUnits:
    """Convert one EDI quantity to Tidewater's canonical internal unit.

    >>> normalize_edi_units(EDIQuantity(Decimal("10"), "kg", "204"))
    NormalizedUnits(quantity=Decimal('22.05'), canonical_unit='LB')
    """
    if item.quantity < 0:
        raise ValueError("quantity cannot be negative")

    code = _effective_code(item)
    value = item.quantity

    if code in {"LB", "LBS"}:
        return _normalize_weight(value, Decimal("1"))
    if code == "KG":
        return _normalize_weight(value, KG_TO_LB)
    if code in {"IN", "INH"}:
        return _normalize_dimension(value, Decimal("1"))
    if code == "FT":
        return _normalize_dimension(value, FT_TO_IN)
    if code == "M":
        return _normalize_dimension(value, M_TO_IN)
    if code == "CM":
        return _normalize_dimension(value, CM_TO_IN)
    if code in {"EA", "CT", "PLT", "PC"}:
        return _normalize_count(value)

    raise ValueError(f"unsupported unit_code {code}")
