from decimal import Decimal

import pytest

from seal_requirement_check import (
    SealRequirementInput,
    evaluate_seal_requirement_check,
)


def make_check(**overrides):
    base = dict(
        commodity="general",
        customer="standard shipper",
        origin_country="US",
        destination_country="US",
        equipment_type="dry_van",
        declared_value_usd=Decimal("5000.00"),
        weight_lb=Decimal("1000"),
        pallet_count=Decimal("1.0"),
        hazmat_division=None,
        ctpat_member=False,
        bonded_shipment=False,
        is_return=False,
    )
    base.update(overrides)
    return SealRequirementInput(**base)


def test_high_value_at_threshold_requires_seal():
    result = evaluate_seal_requirement_check(
        make_check(declared_value_usd=Decimal("100000.00"))
    )
    assert result.required is True
    assert result.reason_code == "high_value"


def test_severe_hazmat_requires_seal():
    result = evaluate_seal_requirement_check(make_check(hazmat_division="2.3"))
    assert result.required is True
    assert result.reason_code == "hazmat_security"


def test_sensitive_commodity_on_tank_is_not_sealable():
    result = evaluate_seal_requirement_check(
        make_check(commodity="pharma", equipment_type="tank")
    )
    assert result.required is False
    assert result.reason_code == "equipment_not_sealable"


def test_cross_border_bulk_equipment_is_exempt():
    result = evaluate_seal_requirement_check(
        make_check(destination_country="CA", equipment_type="hopper")
    )
    assert result.required is False
    assert result.reason_code == "bulk_cross_border_exempt"


def test_cross_border_dry_van_requires_seal():
    result = evaluate_seal_requirement_check(make_check(destination_country="MX"))
    assert result.required is True
    assert result.reason_code == "cross_border"


def test_security_program_requires_seal_on_sealable_equipment():
    result = evaluate_seal_requirement_check(make_check(ctpat_member=True, equipment_type="reefer"))
    assert result.required is True
    assert result.reason_code == "security_program"


def test_produce_requires_seal_at_weight_threshold():
    result = evaluate_seal_requirement_check(
        make_check(commodity="produce", weight_lb=Decimal("10000"))
    )
    assert result.required is True
    assert result.reason_code == "produce_food_safety"


def test_hartline_return_under_two_pallets_is_exempt():
    result = evaluate_seal_requirement_check(
        make_check(
            customer="Hartline Retail",
            is_return=True,
            pallet_count=Decimal("1.9"),
        )
    )
    assert result.required is False
    assert result.reason_code == "customer_return_exempt"


def test_hartline_at_five_pallets_requires_seal():
    result = evaluate_seal_requirement_check(
        make_check(customer="Hartline Retail", pallet_count=Decimal("5.0"))
    )
    assert result.required is True
    assert result.reason_code == "customer_policy"


def test_negative_value_is_rejected():
    with pytest.raises(ValueError):
        evaluate_seal_requirement_check(
            make_check(declared_value_usd=Decimal("-0.01"))
        )
