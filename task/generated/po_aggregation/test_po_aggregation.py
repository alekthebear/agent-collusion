from datetime import date
from decimal import Decimal

import pytest

from po_aggregation import ConsolidationRules, PurchaseOrderLine, aggregate_purchase_orders


def line(**overrides):
    base = dict(
        customer_id="C1",
        purchase_order="PO1",
        sku="SKU1",
        quantity=1,
        weight_lb=Decimal("10.0"),
        extended_value=Decimal("100.00"),
        ship_date=date(2026, 4, 1),
        batch_id="B1",
    )
    base.update(overrides)
    return PurchaseOrderLine(**base)


def test_groups_split_by_ship_date_when_enabled():
    rules = {"C1": ConsolidationRules(split_by_ship_date=True)}
    rows = aggregate_purchase_orders(
        [line(), line(purchase_order="PO2", ship_date=date(2026, 4, 2))], rules
    )
    assert len(rows) == 2
    assert rows[0].ship_date == date(2026, 4, 1)
    assert rows[1].ship_date == date(2026, 4, 2)


def test_groups_ignore_ship_date_when_customer_does_not_split():
    rules = {"C1": ConsolidationRules(split_by_ship_date=False)}
    rows = aggregate_purchase_orders(
        [line(), line(purchase_order="PO2", ship_date=date(2026, 4, 2))], rules
    )
    assert len(rows) == 1
    assert rows[0].ship_date is None
    assert rows[0].po_count == 2


def test_zero_quantity_line_counts_but_does_not_trigger_minimum_billable_floor():
    rows = aggregate_purchase_orders(
        [line(quantity=0, extended_value=Decimal("40.00"), weight_lb=Decimal("2.4"))], {}
    )
    assert rows[0].line_count == 1
    assert rows[0].po_count == 1
    assert rows[0].billed_value == Decimal("40.00")


def test_minimum_billable_value_applies_when_quantity_is_positive():
    rows = aggregate_purchase_orders(
        [line(quantity=2, extended_value=Decimal("40.00"))],
        {"C1": ConsolidationRules(minimum_billable_value=Decimal("250.00"))},
    )
    assert rows[0].merchandise_value == Decimal("40.00")
    assert rows[0].billed_value == Decimal("250.00")


def test_high_value_surcharge_applies_at_threshold_after_floor():
    rows = aggregate_purchase_orders(
        [line(quantity=1, extended_value=Decimal("200.00"))],
        {
            "C1": ConsolidationRules(
                minimum_billable_value=Decimal("5000.00"),
                high_value_threshold=Decimal("5000.00"),
                handling_surcharge_rate=Decimal("0.015"),
            )
        },
    )
    assert rows[0].billed_value == Decimal("5000.00")
    assert rows[0].surcharge == Decimal("75.00")


def test_blank_po_and_sku_are_excluded_from_distinct_counts():
    rows = aggregate_purchase_orders(
        [line(purchase_order="   ", sku=""), line(purchase_order="PO2", sku="SKU2")], {}
    )
    assert rows[0].po_count == 1
    assert rows[0].sku_count == 1


def test_weight_rounds_after_aggregation_half_up():
    rows = aggregate_purchase_orders(
        [line(weight_lb=Decimal("10.2")), line(purchase_order="PO2", weight_lb=Decimal("10.3"))], {}
    )
    assert rows[0].total_weight_lb == Decimal("21")


def test_exceeding_po_limit_marks_group_not_consolidated():
    rows = aggregate_purchase_orders(
        [line(purchase_order=f"PO{i}") for i in range(1, 6)],
        {"C1": ConsolidationRules(max_pos_for_consolidation=4)},
    )
    assert rows[0].po_count == 5
    assert rows[0].consolidated is False


def test_negative_values_are_rejected():
    with pytest.raises(ValueError):
        aggregate_purchase_orders([line(weight_lb=Decimal("-1"))], {})
