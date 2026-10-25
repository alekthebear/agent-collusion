"""Normalize EDI 210 freight invoice line items into invoice charge categories.

Business rules:
- Carriers send line items with an EDI accessorial code, a free-text description, and an amount.
- Negative amounts are treated as credits and map to the ``credit`` category regardless of code.
- Zero-dollar lines map to ``ignore`` because they do not affect settlement.
- The line-haul code ``400`` normally maps to ``linehaul`` but maps to ``fuel`` when the
  description clearly says fuel surcharge.
- Known accessorial codes map directly: ``405`` and ``FSC`` to fuel, ``DET`` and ``DLY`` to
  detention, ``LUM`` and ``HND`` to lumper, ``TON`` to overweight, ``STP`` to stopoff,
  ``LAY`` to layover, ``BOR`` to border, and ``MSC`` to misc.
- Description keywords can override an unknown or generic code. Description matching is case-
  insensitive and checks practical phrases used by billing teams.
- Small positive uncoded amounts under $25.00 default to ``misc``; amounts from $25.00 and up
  default to ``other``. Generic code ``999`` follows the same fallback.
- If both code and description suggest different non-credit categories, the description wins only
  for clear fuel, detention, and lumper phrases; otherwise the explicit code wins.
- Amounts are rounded to cents with half-up rounding before threshold checks.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
SMALL_MISC_LIMIT = Decimal("25.00")


@dataclass(frozen=True)
class EDI210ChargeLine:
    amount: Decimal
    code: str | None = None
    description: str = ""


@dataclass(frozen=True)
class MappedCharge:
    category: str
    normalized_amount: Decimal
    source: str


def _normalize_amount(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _clean_code(code: str | None) -> str:
    if code is None:
        return ""
    return code.strip().upper()


def _clean_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _category_from_description(text: str) -> str | None:
    if not text:
        return None
    if "fuel surcharge" in text or text == "fuel" or text.startswith("fsc"):
        return "fuel"
    if "detention" in text or "delay time" in text or "driver delay" in text:
        return "detention"
    if "lumper" in text or "unloading" in text or "loading assist" in text:
        return "lumper"
    if "line haul" in text or "linehaul" in text or text == "freight":
        return "linehaul"
    if "stop off" in text or "stopoff" in text:
        return "stopoff"
    return None


def _category_from_code(code: str) -> str | None:
    code_map = {
        "400": "linehaul",
        "405": "fuel",
        "FSC": "fuel",
        "DET": "detention",
        "DLY": "detention",
        "LUM": "lumper",
        "HND": "lumper",
        "TON": "overweight",
        "STP": "stopoff",
        "LAY": "layover",
        "BOR": "border",
        "MSC": "misc",
    }
    return code_map.get(code)


def _fallback_category(amount: Decimal) -> str:
    if amount < SMALL_MISC_LIMIT:
        return "misc"
    return "other"


def map_edi_210_charges(line: EDI210ChargeLine) -> MappedCharge:
    """Map one EDI 210 charge line to a normalized invoice category.

    Returns the chosen category, the rounded amount, and a short source marker showing
    which rule decided the mapping.
    """
    amount = _normalize_amount(line.amount)
    if amount < Decimal("0.00"):
        return MappedCharge("credit", amount, "amount")
    if amount == Decimal("0.00"):
        return MappedCharge("ignore", amount, "amount")

    code = _clean_code(line.code)
    text = _clean_text(line.description)
    desc_category = _category_from_description(text)
    code_category = _category_from_code(code)

    if code == "400" and desc_category == "fuel":
        return MappedCharge("fuel", amount, "description")

    if desc_category in {"fuel", "detention", "lumper"}:
        if code_category is None or code_category == "misc" or code == "999":
            return MappedCharge(desc_category, amount, "description")

    if code_category is not None:
        return MappedCharge(code_category, amount, "code")

    if desc_category is not None:
        return MappedCharge(desc_category, amount, "description")

    if code == "999" or code == "":
        return MappedCharge(_fallback_category(amount), amount, "fallback")

    return MappedCharge("other", amount, "fallback")
