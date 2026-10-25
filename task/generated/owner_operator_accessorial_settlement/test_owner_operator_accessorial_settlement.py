from decimal import Decimal

import pytest

from owner_operator_accessorial_settlement import (
    AccessorialItem,
    SettlementTerms,
    calculate_owner_operator_accessorial_settlement,
)


def test_negative_billed_amount_is_rejected():
    with pytest.raises(ValueError):
        calculate_owner_operator_accessorial_settlement(
            AccessorialItem(code="detention", billed_amount=Decimal("-1.00"))
        )


def test_fuel_surcharge_never_pays():
    item = AccessorialItem(code="FSC", billed_amount=Decimal("123.45"))
    assert calculate_owner_operator_accessorial_settlement(item) == Decimal("0.00")


def test_lumper_requires_receipt_for_full_reimbursement():
    missing = AccessorialItem(code="lumper", billed_amount=Decimal("89.17"), has_receipt=False)
    present = AccessorialItem(code="lumper", billed_amount=Decimal("89.17"), has_receipt=True)
    assert calculate_owner_operator_accessorial_settlement(missing) == Decimal("0.00")
    assert calculate_owner_operator_accessorial_settlement(present) == Decimal("89.17")


def test_detention_below_minimum_threshold_pays_zero():
    item = AccessorialItem(code="detention", billed_amount=Decimal("49.99"))
    assert calculate_owner_operator_accessorial_settlement(item) == Decimal("0.00")


def test_detention_at_threshold_pays_percentage():
    item = AccessorialItem(code="detention", billed_amount=Decimal("50.00"))
    assert calculate_owner_operator_accessorial_settlement(item) == Decimal("35.00")


def test_tonu_requires_truck_on_time():
    late = AccessorialItem(code="tonu", billed_amount=Decimal("200.00"), truck_on_time=False)
    on_time = AccessorialItem(code="tonu", billed_amount=Decimal("200.00"), truck_on_time=True)
    assert calculate_owner_operator_accessorial_settlement(late) == Decimal("0.00")
    assert calculate_owner_operator_accessorial_settlement(on_time) == Decimal("150.00")


def test_layover_only_pays_on_amount_above_deductible():
    item = AccessorialItem(code="layover", billed_amount=Decimal("200.00"))
    assert calculate_owner_operator_accessorial_settlement(item) == Decimal("30.00")


def test_driver_assist_is_capped_after_percentage():
    item = AccessorialItem(code="driver assist", billed_amount=Decimal("600.00"))
    assert calculate_owner_operator_accessorial_settlement(item) == Decimal("250.00")


def test_unknown_code_uses_default_percentage_with_half_up_rounding():
    item = AccessorialItem(code="escort", billed_amount=Decimal("10.05"))
    assert calculate_owner_operator_accessorial_settlement(item) == Decimal("6.53")


def test_grace_period_zeros_small_payables_only_after_item_rules():
    terms = SettlementTerms(in_grace_period=True)
    small = AccessorialItem(code="escort", billed_amount=Decimal("30.00"))
    large = AccessorialItem(code="layover", billed_amount=Decimal("200.00"))
    assert calculate_owner_operator_accessorial_settlement(small, terms) == Decimal("0.00")
    assert calculate_owner_operator_accessorial_settlement(large, terms) == Decimal("30.00")
