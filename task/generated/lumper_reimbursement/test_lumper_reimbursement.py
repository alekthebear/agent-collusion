from decimal import Decimal

import pytest

from lumper_reimbursement import (
    LumperReceipt,
    ReimbursementTerms,
    calculate_lumper_reimbursement,
)


def test_standard_receipt_gets_markup_on_customer_bill():
    result = calculate_lumper_reimbursement(LumperReceipt(lumper_fee=Decimal("120.00")))
    assert result.carrier_pay == Decimal("120.00")
    assert result.customer_bill == Decimal("132.00")
    assert result.denied_amount == Decimal("0.00")


def test_non_reimbursable_charges_are_denied():
    receipt = LumperReceipt(
        lumper_fee=Decimal("80.00"),
        late_fee=Decimal("10.00"),
        parking_fee=Decimal("5.00"),
        tip=Decimal("3.00"),
    )
    result = calculate_lumper_reimbursement(receipt)
    assert result.carrier_pay == Decimal("80.00")
    assert result.customer_bill == Decimal("88.00")
    assert result.denied_amount == Decimal("18.00")


def test_no_receipt_under_limit_is_allowed():
    receipt = LumperReceipt(lumper_fee=Decimal("25.05"), receipt_provided=False)
    result = calculate_lumper_reimbursement(receipt)
    assert result.carrier_pay == Decimal("25.05")
    assert result.customer_bill == Decimal("27.56")
    assert result.denied_amount == Decimal("0.00")


def test_no_receipt_over_tolerance_is_denied_in_full():
    receipt = LumperReceipt(lumper_fee=Decimal("25.06"), receipt_provided=False)
    result = calculate_lumper_reimbursement(receipt)
    assert result.carrier_pay == Decimal("0.00")
    assert result.customer_bill == Decimal("0.00")
    assert result.denied_amount == Decimal("25.06")


def test_approval_limit_caps_carrier_pay_without_preapproval():
    receipt = LumperReceipt(lumper_fee=Decimal("340.00"))
    result = calculate_lumper_reimbursement(receipt)
    assert result.carrier_pay == Decimal("300.00")
    assert result.customer_bill == Decimal("330.00")
    assert result.denied_amount == Decimal("40.00")


def test_amount_within_limit_tolerance_is_not_capped():
    receipt = LumperReceipt(lumper_fee=Decimal("300.05"))
    result = calculate_lumper_reimbursement(receipt)
    assert result.carrier_pay == Decimal("300.05")
    assert result.customer_bill == Decimal("330.06")
    assert result.denied_amount == Decimal("0.00")


def test_preapproved_over_limit_allows_full_reimbursement():
    receipt = LumperReceipt(lumper_fee=Decimal("340.00"), preapproved_over_limit=True)
    result = calculate_lumper_reimbursement(receipt)
    assert result.carrier_pay == Decimal("340.00")
    assert result.customer_bill == Decimal("374.00")
    assert result.denied_amount == Decimal("0.00")


def test_pass_through_only_skips_markup_and_honors_customer_cap():
    terms = ReimbursementTerms(pass_through_only=True, max_customer_bill=Decimal("90.00"))
    result = calculate_lumper_reimbursement(LumperReceipt(lumper_fee=Decimal("120.00")), terms)
    assert result.carrier_pay == Decimal("120.00")
    assert result.customer_bill == Decimal("90.00")
    assert result.denied_amount == Decimal("0.00")


def test_negative_amounts_are_rejected():
    with pytest.raises(ValueError):
        calculate_lumper_reimbursement(LumperReceipt(lumper_fee=Decimal("-1.00")))
