from decimal import Decimal

import pytest

from washout_fee import PassThroughTerms, WashoutRequest, calculate_washout_fee


def test_dry_freight_without_operational_requirement_is_not_reimbursed():
    request = WashoutRequest(
        commodity_class="dry",
        required_wash_level="none",
        receipt_amount=Decimal("22.00"),
    )
    assert calculate_washout_fee(request) == Decimal("0.00")


def test_operations_requirement_can_create_reimbursement_for_dry_freight():
    request = WashoutRequest(
        commodity_class="dry",
        required_wash_level="rinse",
        receipt_amount=Decimal("30.00"),
    )
    assert calculate_washout_fee(request) == Decimal("15.00")


def test_stronger_commodity_class_controls_required_level():
    request = WashoutRequest(
        commodity_class="chemical",
        required_wash_level="rinse",
        receipt_amount=Decimal("100.00"),
    )
    assert calculate_washout_fee(request) == Decimal("70.00")


def test_food_grade_trailer_forces_at_least_sanitize():
    request = WashoutRequest(
        commodity_class="produce",
        required_wash_level="rinse",
        receipt_amount=Decimal("140.00"),
        food_grade_trailer=True,
    )
    assert calculate_washout_fee(request) == Decimal("125.00")


def test_hazmat_premium_can_be_disallowed_by_contract():
    request = WashoutRequest(
        commodity_class="hazmat",
        required_wash_level="hazmat",
        receipt_amount=Decimal("220.00"),
    )
    terms = PassThroughTerms(allow_hazmat_premium=False)
    assert calculate_washout_fee(request, terms) == Decimal("70.00")


def test_customer_cap_limits_allowed_amount_before_deductible():
    request = WashoutRequest(
        commodity_class="food",
        required_wash_level="sanitize",
        receipt_amount=Decimal("130.00"),
    )
    terms = PassThroughTerms(customer_cap=Decimal("90.00"))
    assert calculate_washout_fee(request, terms) == Decimal("75.00")


def test_receipt_at_deductible_reimburses_zero():
    request = WashoutRequest(
        commodity_class="produce",
        required_wash_level="rinse",
        receipt_amount=Decimal("15.00"),
    )
    assert calculate_washout_fee(request) == Decimal("0.00")


def test_pass_through_can_be_fully_disallowed():
    request = WashoutRequest(
        commodity_class="food",
        required_wash_level="sanitize",
        receipt_amount=Decimal("90.00"),
    )
    terms = PassThroughTerms(allow_pass_through=False)
    assert calculate_washout_fee(request, terms) == Decimal("0.00")


def test_negative_receipt_is_rejected():
    request = WashoutRequest(
        commodity_class="chemical",
        required_wash_level="standard",
        receipt_amount=Decimal("-1.00"),
    )
    with pytest.raises(ValueError):
        calculate_washout_fee(request)
