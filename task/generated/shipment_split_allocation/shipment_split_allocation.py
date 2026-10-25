"""Allocate split-shipment amounts across child shipments.

When one customer order is split into multiple child shipments, settlement must apportion
parent totals down to each child. Tidewater uses three allocation methods by field:
weight is usually allocated by actual line weight, linehaul revenue can be allocated by
line count or weight, and flat accessorials are commonly split equally.

Business rules:
- ``total_charge`` and ``total_revenue`` are money and round half up to cents.
- ``total_weight`` is in pounds and rounds half up to whole pounds.
- A field may use ``equal``, ``proportional``, or ``line_based`` allocation.
- ``proportional`` uses child weight shares; if all weights are zero, it falls back to equal.
- ``line_based`` uses child line-count shares; if all line counts are zero, it falls back to equal.
- Any remainder caused by rounding is assigned to the last child so child amounts sum exactly
  to the parent total.
- Negative totals are allowed for credits, but child weights may not be negative.
- At least one child shipment is required.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
POUND = Decimal("1")
ALLOWED_METHODS = {"equal", "proportional", "line_based"}


@dataclass(frozen=True)
class ChildShipment:
    shipment_id: str
    weight: Decimal
    line_count: int = 0


@dataclass(frozen=True)
class SplitTotals:
    total_charge: Decimal
    total_weight: Decimal
    total_revenue: Decimal


@dataclass(frozen=True)
class AllocationRules:
    charge_method: str = "equal"
    weight_method: str = "proportional"
    revenue_method: str = "line_based"


@dataclass(frozen=True)
class ShipmentAllocation:
    shipment_id: str
    charge: Decimal
    weight: Decimal
    revenue: Decimal


def _validate(children: list[ChildShipment], totals: SplitTotals, rules: AllocationRules) -> None:
    if not children:
        raise ValueError("at least one child shipment is required")
    for method in (rules.charge_method, rules.weight_method, rules.revenue_method):
        if method not in ALLOWED_METHODS:
            raise ValueError(f"unsupported allocation method: {method}")
    if totals.total_weight < 0:
        raise ValueError("total_weight cannot be negative")
    for child in children:
        if child.weight < 0:
            raise ValueError(f"child weight cannot be negative: {child.shipment_id}")
        if child.line_count < 0:
            raise ValueError(f"line_count cannot be negative: {child.shipment_id}")


def _basis(children: list[ChildShipment], method: str) -> list[Decimal]:
    if method == "equal":
        return [Decimal("1")] * len(children)
    if method == "proportional":
        weights = [child.weight for child in children]
        return weights if sum(weights, Decimal("0")) > 0 else [Decimal("1")] * len(children)
    line_counts = [Decimal(child.line_count) for child in children]
    return line_counts if sum(line_counts, Decimal("0")) > 0 else [Decimal("1")] * len(children)


def _allocate(total: Decimal, bases: list[Decimal], quantum: Decimal) -> list[Decimal]:
    basis_total = sum(bases, Decimal("0"))
    if basis_total == 0:
        bases = [Decimal("1")] * len(bases)
        basis_total = Decimal(len(bases))
    allocated: list[Decimal] = []
    running = Decimal("0")
    for basis in bases[:-1]:
        share = (total * basis / basis_total).quantize(quantum, rounding=ROUND_HALF_UP)
        allocated.append(share)
        running += share
    allocated.append((total - running).quantize(quantum, rounding=ROUND_HALF_UP))
    return allocated


def allocate_shipment_split(
    children: list[ChildShipment],
    totals: SplitTotals,
    rules: AllocationRules = AllocationRules(),
) -> list[ShipmentAllocation]:
    """Allocate parent totals to child shipments with exact summed results.

    >>> kids = [ChildShipment("A", Decimal("100"), 1), ChildShipment("B", Decimal("300"), 3)]
    >>> allocate_shipment_split(kids, SplitTotals(Decimal("10.00"), Decimal("400"), Decimal("40.00")))
    [ShipmentAllocation(shipment_id='A', charge=Decimal('5.00'), weight=Decimal('100'), revenue=Decimal('10.00')), ShipmentAllocation(shipment_id='B', charge=Decimal('5.00'), weight=Decimal('300'), revenue=Decimal('30.00'))]
    """
    _validate(children, totals, rules)
    charge_alloc = _allocate(totals.total_charge, _basis(children, rules.charge_method), CENT)
    weight_alloc = _allocate(totals.total_weight, _basis(children, rules.weight_method), POUND)
    revenue_alloc = _allocate(totals.total_revenue, _basis(children, rules.revenue_method), CENT)
    return [
        ShipmentAllocation(
            shipment_id=child.shipment_id,
            charge=charge_alloc[i],
            weight=weight_alloc[i],
            revenue=revenue_alloc[i],
        )
        for i, child in enumerate(children)
    ]
