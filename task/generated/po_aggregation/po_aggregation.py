"""Aggregate purchase-order metrics for shipment billing and customer reporting.

Each shipment line may reference a purchase order, customer, weight and extended value.
Billing and scorecard feeds group lines by customer and optionally by a consolidation key,
usually the ship date or a route-level batch identifier. Lines with the same effective group
collapse into one summary row with distinct PO and SKU counts plus billable totals.

Business rules used by Tidewater's shared reporting jobs:
- A line with quantity 0 is informational and contributes to distinct counts only.
- Negative quantity or negative weight/value is invalid.
- Weight is rounded to the nearest whole pound, half up, after aggregation.
- Money is rounded to cents, half up, after aggregation.
- Distinct counts ignore blank PO numbers and blank SKU codes.
- Customers marked ``split_by_ship_date`` form separate groups per ship date; otherwise ship
  date differences do not split a group.
- If a group's total value is below ``minimum_billable_value`` and it has billable quantity,
  the billed value is raised to that floor.
- Groups at or above ``high_value_threshold`` receive a handling surcharge rate applied to the
  billed value after any minimum floor.
- When ``max_pos_for_consolidation`` is exceeded, the group is still returned but flagged as
  not consolidated so downstream billing can review it.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
POUND = Decimal("1")


@dataclass(frozen=True)
class PurchaseOrderLine:
    customer_id: str
    purchase_order: str
    sku: str
    quantity: int
    weight_lb: Decimal
    extended_value: Decimal
    ship_date: date
    batch_id: str = ""


@dataclass(frozen=True)
class ConsolidationRules:
    split_by_ship_date: bool = True
    minimum_billable_value: Decimal = Decimal("250.00")
    high_value_threshold: Decimal = Decimal("5000.00")
    handling_surcharge_rate: Decimal = Decimal("0.015")
    max_pos_for_consolidation: int = 4


@dataclass(frozen=True)
class PurchaseOrderSummary:
    customer_id: str
    group_key: str
    ship_date: date | None
    po_count: int
    sku_count: int
    line_count: int
    total_quantity: int
    total_weight_lb: Decimal
    merchandise_value: Decimal
    billed_value: Decimal
    surcharge: Decimal
    consolidated: bool


def _clean(text: str) -> str:
    return text.strip()


def _validate_line(line: PurchaseOrderLine) -> None:
    if not _clean(line.customer_id):
        raise ValueError("customer_id is required")
    if line.quantity < 0:
        raise ValueError("quantity cannot be negative")
    if line.weight_lb < 0 or line.extended_value < 0:
        raise ValueError("weight and value cannot be negative")


def _group_key(line: PurchaseOrderLine, rules: ConsolidationRules) -> tuple[str, str, date | None]:
    batch = _clean(line.batch_id) or "default"
    ship_date = line.ship_date if rules.split_by_ship_date else None
    return line.customer_id, batch, ship_date


def _q_money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _q_weight(weight: Decimal) -> Decimal:
    return weight.quantize(POUND, rounding=ROUND_HALF_UP)


def aggregate_purchase_orders(
    lines: list[PurchaseOrderLine],
    rules_by_customer: dict[str, ConsolidationRules],
) -> list[PurchaseOrderSummary]:
    """Aggregate shipment lines into purchase-order billing groups."""
    buckets: dict[tuple[str, str, date | None], dict] = {}
    for line in lines:
        _validate_line(line)
        rules = rules_by_customer.get(line.customer_id, ConsolidationRules())
        key = _group_key(line, rules)
        bucket = buckets.setdefault(
            key,
            {
                "rules": rules,
                "pos": set(),
                "skus": set(),
                "line_count": 0,
                "quantity": 0,
                "weight": Decimal("0"),
                "value": Decimal("0"),
            },
        )
        bucket["line_count"] += 1
        bucket["quantity"] += line.quantity
        bucket["weight"] += line.weight_lb
        bucket["value"] += line.extended_value
        po = _clean(line.purchase_order)
        sku = _clean(line.sku)
        if po:
            bucket["pos"].add(po)
        if sku:
            bucket["skus"].add(sku)

    summaries: list[PurchaseOrderSummary] = []
    for (customer_id, batch, ship_date), bucket in sorted(buckets.items()):
        rules = bucket["rules"]
        merchandise_value = _q_money(bucket["value"])
        billed_value = merchandise_value
        if bucket["quantity"] > 0 and billed_value < rules.minimum_billable_value:
            billed_value = _q_money(rules.minimum_billable_value)
        surcharge = Decimal("0.00")
        if billed_value >= rules.high_value_threshold:
            surcharge = _q_money(billed_value * rules.handling_surcharge_rate)
        summaries.append(
            PurchaseOrderSummary(
                customer_id=customer_id,
                group_key=batch,
                ship_date=ship_date,
                po_count=len(bucket["pos"]),
                sku_count=len(bucket["skus"]),
                line_count=bucket["line_count"],
                total_quantity=bucket["quantity"],
                total_weight_lb=_q_weight(bucket["weight"]),
                merchandise_value=merchandise_value,
                billed_value=billed_value,
                surcharge=surcharge,
                consolidated=len(bucket["pos"]) <= rules.max_pos_for_consolidation,
            )
        )
    return summaries
