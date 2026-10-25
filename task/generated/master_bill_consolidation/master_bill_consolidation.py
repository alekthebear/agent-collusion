"""Master bill consolidation for customer invoicing.

When several child shipments move under one master bill, customer billing rolls the
children into a single payable total. Standard Tidewater rules are:
- A child marked cancelled never bills and does not count toward thresholds.
- Duplicate charges from connected child shipments are suppressed by duplicate key;
  for a given key we keep the highest billable amount among non-cancelled children.
- Fuel surcharges bill at 12% of linehaul, except expedited children use 18%.
- Hazmat adds a flat 35.00 per applicable child after duplicate suppression.
- Residential delivery adds 22.50 per applicable child, but is waived when that
  child's weight is under 200 lb.
- If consolidated billable weight reaches 10,000 lb, apply a 3% volume discount to
  the subtotal before any minimum invoice check.
- The final invoice has a minimum of 150.00 whenever at least one non-cancelled
  child remains; if none remain, the total is 0.00.
All currency is rounded half-up to cents at each child-charge calculation and on the
final total.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
FUEL_STANDARD = Decimal("0.12")
FUEL_EXPEDITED = Decimal("0.18")
HAZMAT_FEE = Decimal("35.00")
RESIDENTIAL_FEE = Decimal("22.50")
WEIGHT_DISCOUNT_THRESHOLD = 10000
VOLUME_DISCOUNT = Decimal("0.03")
MINIMUM_INVOICE = Decimal("150.00")


@dataclass(frozen=True)
class ChildShipment:
    shipment_id: str
    weight_lb: int
    linehaul: Decimal
    expedited: bool = False
    hazmat: bool = False
    residential: bool = False
    cancelled: bool = False
    duplicate_key: str | None = None


@dataclass(frozen=True)
class ConsolidationResult:
    billable_children: int
    consolidated_weight_lb: int
    linehaul_total: Decimal
    accessorial_total: Decimal
    discount_total: Decimal
    final_total: Decimal


def _money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate_child(child: ChildShipment) -> None:
    if child.weight_lb < 0:
        raise ValueError(f"weight_lb must be non-negative for {child.shipment_id}")
    if child.linehaul < Decimal("0.00"):
        raise ValueError(f"linehaul must be non-negative for {child.shipment_id}")
    if child.duplicate_key == "":
        raise ValueError(f"duplicate_key cannot be empty for {child.shipment_id}")


def _child_accessorials(child: ChildShipment) -> Decimal:
    fuel_rate = FUEL_EXPEDITED if child.expedited else FUEL_STANDARD
    fuel = _money(child.linehaul * fuel_rate)
    hazmat = HAZMAT_FEE if child.hazmat else Decimal("0.00")
    residential = (
        RESIDENTIAL_FEE if child.residential and child.weight_lb >= 200 else Decimal("0.00")
    )
    return _money(fuel + hazmat + residential)


def _child_amount(child: ChildShipment) -> Decimal:
    return _money(child.linehaul + _child_accessorials(child))


def _surviving_children(children: list[ChildShipment]) -> list[ChildShipment]:
    singles: list[ChildShipment] = []
    deduped: dict[str, tuple[Decimal, ChildShipment]] = {}
    for child in children:
        _validate_child(child)
        if child.cancelled:
            continue
        if child.duplicate_key is None:
            singles.append(child)
            continue
        score = _child_accessorials(child)
        current = deduped.get(child.duplicate_key)
        if current is None or score > current[0] or (score == current[0] and child.weight_lb > current[1].weight_lb):
            deduped[child.duplicate_key] = (score, child)
    return singles + [entry[1] for entry in deduped.values()]


def calculate_master_bill_consolidation(children: list[ChildShipment]) -> ConsolidationResult:
    """Return rolled-up billing totals for one master bill."""
    survivors = _surviving_children(children)
    if not survivors:
        zero = Decimal("0.00")
        return ConsolidationResult(0, 0, zero, zero, zero, zero)

    linehaul_total = Decimal("0.00")
    gross_total = Decimal("0.00")
    weight_total = 0
    for child in survivors:
        linehaul_total += child.linehaul
        gross_total += _child_amount(child)
        weight_total += child.weight_lb

    linehaul_total = _money(linehaul_total)
    gross_total = _money(gross_total)
    discount_total = Decimal("0.00")
    if weight_total >= WEIGHT_DISCOUNT_THRESHOLD:
        discount_total = _money(gross_total * VOLUME_DISCOUNT)
    final_total = gross_total - discount_total
    if final_total < MINIMUM_INVOICE:
        final_total = MINIMUM_INVOICE
    final_total = _money(final_total)
    accessorial_total = _money(gross_total - linehaul_total)
    return ConsolidationResult(
        billable_children=len(survivors),
        consolidated_weight_lb=weight_total,
        linehaul_total=linehaul_total,
        accessorial_total=accessorial_total,
        discount_total=discount_total,
        final_total=final_total,
    )
