from decimal import Decimal

import pytest

from master_bill_consolidation import (
    ChildShipment,
    calculate_master_bill_consolidation,
)


def test_cancelled_children_do_not_bill_or_count():
    result = calculate_master_bill_consolidation(
        [ChildShipment("C1", 500, Decimal("100.00"), cancelled=True)]
    )
    assert result.billable_children == 0
    assert result.consolidated_weight_lb == 0
    assert result.final_total == Decimal("0.00")


def test_standard_fuel_applies_and_minimum_invoice_can_raise_total():
    result = calculate_master_bill_consolidation(
        [ChildShipment("C1", 900, Decimal("100.00"))]
    )
    assert result.linehaul_total == Decimal("100.00")
    assert result.accessorial_total == Decimal("12.00")
    assert result.final_total == Decimal("150.00")


def test_expedited_uses_higher_fuel_rate():
    result = calculate_master_bill_consolidation(
        [ChildShipment("C1", 900, Decimal("200.00"), expedited=True)]
    )
    assert result.accessorial_total == Decimal("36.00")
    assert result.final_total == Decimal("236.00")


def test_hazmat_and_residential_apply_when_eligible():
    result = calculate_master_bill_consolidation(
        [ChildShipment("C1", 300, Decimal("200.00"), hazmat=True, residential=True)]
    )
    assert result.accessorial_total == Decimal("81.50")
    assert result.final_total == Decimal("281.50")


def test_residential_is_waived_under_200_lb():
    result = calculate_master_bill_consolidation(
        [ChildShipment("C1", 199, Decimal("200.00"), residential=True)]
    )
    assert result.accessorial_total == Decimal("24.00")
    assert result.final_total == Decimal("224.00")


def test_duplicate_key_keeps_higher_billable_amount():
    result = calculate_master_bill_consolidation(
        [
            ChildShipment("C1", 500, Decimal("300.00"), duplicate_key="D1"),
            ChildShipment("C2", 500, Decimal("250.00"), hazmat=True, duplicate_key="D1"),
        ]
    )
    assert result.billable_children == 1
    assert result.linehaul_total == Decimal("250.00")
    assert result.accessorial_total == Decimal("65.00")
    assert result.final_total == Decimal("315.00")


def test_duplicate_tie_breaker_keeps_heavier_child_on_equal_amount():
    result = calculate_master_bill_consolidation(
        [
            ChildShipment("C1", 400, Decimal("100.00"), duplicate_key="D1"),
            ChildShipment("C2", 700, Decimal("100.00"), duplicate_key="D1"),
        ]
    )
    assert result.billable_children == 1
    assert result.consolidated_weight_lb == 700
    assert result.final_total == Decimal("150.00")


def test_volume_discount_applies_at_threshold_weight():
    result = calculate_master_bill_consolidation(
        [
            ChildShipment("C1", 6000, Decimal("500.00")),
            ChildShipment("C2", 4000, Decimal("500.00")),
        ]
    )
    assert result.consolidated_weight_lb == 10000
    assert result.discount_total == Decimal("33.60")
    assert result.final_total == Decimal("1086.40")


def test_negative_linehaul_is_rejected():
    with pytest.raises(ValueError):
        calculate_master_bill_consolidation(
            [ChildShipment("C1", 100, Decimal("-1.00"))]
        )


def test_empty_duplicate_key_is_rejected():
    with pytest.raises(ValueError):
        calculate_master_bill_consolidation(
            [ChildShipment("C1", 100, Decimal("10.00"), duplicate_key="")]
        )
