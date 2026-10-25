"""Brokerage fees for cross-border customs entries.

Tidewater invoices brokerage on import crossings as a base customs-entry fee plus
possible adders for extra entries, complex commodities, tariff review, and selected
pass-through filing costs. The standard rules used by settlement are:

- The first customs entry is included in the lane's base fee; each additional entry
  adds an entry surcharge.
- Informal crossings are cheaper than formal crossings.
- Complex commodities (regulated, food, textile, high-value mixed loads) add a flat
  review fee, but only when there is at least one entry.
- Tariff treatment is mutually exclusive:
  * "standard" adds nothing.
  * "section_301" adds a tariff-review fee.
  * "anti_dumping" adds a higher special-case review fee.
- A customs bond is billed through at cost when required, but waived on informal
  crossings valued under $2,500.
- Formal crossings valued above $250,000 incur a high-value filing surcharge.
- Brokerage is capped for standard tariff work, but anti-dumping files are uncapped
  because outside specialists may be involved.
- Final amounts are rounded half up to the cent.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
INFORMAL_BASE_FEE = Decimal("42.00")
FORMAL_BASE_FEE = Decimal("118.00")
ADDITIONAL_ENTRY_FEE = Decimal("18.50")
COMPLEX_COMMODITY_FEE = Decimal("27.25")
SECTION_301_REVIEW_FEE = Decimal("33.40")
ANTI_DUMPING_REVIEW_FEE = Decimal("145.00")
HIGH_VALUE_SURCHARGE = Decimal("55.00")
STANDARD_CAP = Decimal("325.00")
INFORMAL_BOND_WAIVER_VALUE = Decimal("2500.00")
HIGH_VALUE_THRESHOLD = Decimal("250000.00")


@dataclass(frozen=True)
class BrokerageRequest:
    crossing_type: str
    entry_count: int
    commodity_complexity: str
    tariff_treatment: str
    declared_value: Decimal
    customs_bond_required: bool = False
    customs_bond_amount: Decimal = Decimal("0.00")


@dataclass(frozen=True)
class BrokerageTerms:
    informal_base_fee: Decimal = INFORMAL_BASE_FEE
    formal_base_fee: Decimal = FORMAL_BASE_FEE
    additional_entry_fee: Decimal = ADDITIONAL_ENTRY_FEE
    complex_commodity_fee: Decimal = COMPLEX_COMMODITY_FEE
    section_301_review_fee: Decimal = SECTION_301_REVIEW_FEE
    anti_dumping_review_fee: Decimal = ANTI_DUMPING_REVIEW_FEE
    high_value_surcharge: Decimal = HIGH_VALUE_SURCHARGE
    standard_cap: Decimal = STANDARD_CAP


def _validate(request: BrokerageRequest) -> None:
    if request.crossing_type not in {"informal", "formal"}:
        raise ValueError(f"unsupported crossing_type {request.crossing_type!r}")
    if request.entry_count < 0:
        raise ValueError("entry_count cannot be negative")
    if request.commodity_complexity not in {"standard", "complex"}:
        raise ValueError(f"unsupported commodity_complexity {request.commodity_complexity!r}")
    if request.tariff_treatment not in {"standard", "section_301", "anti_dumping"}:
        raise ValueError(f"unsupported tariff_treatment {request.tariff_treatment!r}")
    if request.declared_value < 0:
        raise ValueError("declared_value cannot be negative")
    if request.customs_bond_amount < 0:
        raise ValueError("customs_bond_amount cannot be negative")
    if request.entry_count == 0 and request.customs_bond_required:
        raise ValueError("bond cannot be required when there are no entries")


def _base_fee(crossing_type: str, terms: BrokerageTerms) -> Decimal:
    return terms.informal_base_fee if crossing_type == "informal" else terms.formal_base_fee


def _tariff_fee(tariff_treatment: str, terms: BrokerageTerms) -> Decimal:
    if tariff_treatment == "section_301":
        return terms.section_301_review_fee
    if tariff_treatment == "anti_dumping":
        return terms.anti_dumping_review_fee
    return Decimal("0.00")


def _bond_fee(request: BrokerageRequest) -> Decimal:
    if not request.customs_bond_required:
        return Decimal("0.00")
    if request.crossing_type == "informal" and request.declared_value < INFORMAL_BOND_WAIVER_VALUE:
        return Decimal("0.00")
    return request.customs_bond_amount


def calculate_cross_border_brokerage_fee(
    request: BrokerageRequest, terms: BrokerageTerms = BrokerageTerms()
) -> Decimal:
    """Return brokerage due for one border crossing, rounded to cents."""
    _validate(request)
    if request.entry_count == 0:
        return Decimal("0.00")

    amount = _base_fee(request.crossing_type, terms)
    amount += terms.additional_entry_fee * max(request.entry_count - 1, 0)

    if request.commodity_complexity == "complex":
        amount += terms.complex_commodity_fee

    amount += _tariff_fee(request.tariff_treatment, terms)
    amount += _bond_fee(request)

    if request.crossing_type == "formal" and request.declared_value > HIGH_VALUE_THRESHOLD:
        amount += terms.high_value_surcharge

    amount = amount.quantize(CENT, rounding=ROUND_HALF_UP)
    if request.tariff_treatment != "anti_dumping" and amount > terms.standard_cap:
        return terms.standard_cap
    return amount
