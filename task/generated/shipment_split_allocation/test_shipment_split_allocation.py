from decimal import Decimal

import pytest

from shipment_split_allocation import (
    AllocationRules,
    ChildShipment,
    SplitTotals,
    allocate_shipment_split,
)


def test_equal_charge_split_assigns_remainder_to_last_child():
    children = [
        ChildShipment("A", Decimal("100"), 1),
        ChildShipment("B", Decimal("100"), 1),
        ChildShipment("C", Decimal("100"), 1),
    ]
    totals = SplitTotals(Decimal("10.00"), Decimal("300"), Decimal("0.00"))
    out = allocate_shipment_split(children, totals)
    assert [row.charge for row in out] == [Decimal("3.33"), Decimal("3.33"), Decimal("3.34")]


def test_weight_proportional_allocation_uses_child_weights():
    children = [
        ChildShipment("A", Decimal("125"), 1),
        ChildShipment("B", Decimal("275"), 1),
    ]
    totals = SplitTotals(Decimal("0.00"), Decimal("400"), Decimal("0.00"))
    out = allocate_shipment_split(children, totals)
    assert [row.weight for row in out] == [Decimal("125"), Decimal("275")]


def test_revenue_line_based_allocation_uses_line_counts():
    children = [
        ChildShipment("A", Decimal("100"), 1),
        ChildShipment("B", Decimal("100"), 3),
    ]
    totals = SplitTotals(Decimal("0.00"), Decimal("200"), Decimal("80.00"))
    out = allocate_shipment_split(children, totals)
    assert [row.revenue for row in out] == [Decimal("20.00"), Decimal("60.00")]


def test_zero_weight_proportional_falls_back_to_equal():
    children = [
        ChildShipment("A", Decimal("0"), 1),
        ChildShipment("B", Decimal("0"), 1),
    ]
    totals = SplitTotals(Decimal("0.00"), Decimal("5"), Decimal("0.00"))
    out = allocate_shipment_split(children, totals)
    assert [row.weight for row in out] == [Decimal("3"), Decimal("2")]


def test_zero_line_counts_fall_back_to_equal_for_revenue():
    children = [
        ChildShipment("A", Decimal("10"), 0),
        ChildShipment("B", Decimal("20"), 0),
    ]
    totals = SplitTotals(Decimal("0.00"), Decimal("30"), Decimal("7.00"))
    out = allocate_shipment_split(children, totals)
    assert [row.revenue for row in out] == [Decimal("3.50"), Decimal("3.50")]


def test_negative_total_charge_allocates_credit():
    children = [
        ChildShipment("A", Decimal("50"), 1),
        ChildShipment("B", Decimal("50"), 1),
    ]
    totals = SplitTotals(Decimal("-1.01"), Decimal("100"), Decimal("0.00"))
    out = allocate_shipment_split(children, totals)
    assert [row.charge for row in out] == [Decimal("-0.51"), Decimal("-0.50")]


def test_custom_methods_can_make_charge_proportional_and_revenue_equal():
    children = [
        ChildShipment("A", Decimal("100"), 1),
        ChildShipment("B", Decimal("300"), 5),
    ]
    totals = SplitTotals(Decimal("12.00"), Decimal("400"), Decimal("9.00"))
    rules = AllocationRules(charge_method="proportional", weight_method="proportional", revenue_method="equal")
    out = allocate_shipment_split(children, totals, rules)
    assert [row.charge for row in out] == [Decimal("3.00"), Decimal("9.00")]
    assert [row.revenue for row in out] == [Decimal("4.50"), Decimal("4.50")]


def test_negative_child_weight_is_rejected():
    children = [ChildShipment("A", Decimal("-1"), 1)]
    totals = SplitTotals(Decimal("0.00"), Decimal("0"), Decimal("0.00"))
    with pytest.raises(ValueError):
        allocate_shipment_split(children, totals)


def test_unsupported_method_is_rejected():
    children = [ChildShipment("A", Decimal("1"), 1)]
    totals = SplitTotals(Decimal("0.00"), Decimal("1"), Decimal("0.00"))
    rules = AllocationRules(charge_method="miles")
    with pytest.raises(ValueError):
        allocate_shipment_split(children, totals, rules)


def test_empty_children_are_rejected():
    totals = SplitTotals(Decimal("0.00"), Decimal("0"), Decimal("0.00"))
    with pytest.raises(ValueError):
        allocate_shipment_split([], totals)
