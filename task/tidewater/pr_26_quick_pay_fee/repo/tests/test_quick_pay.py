from datetime import date
from decimal import Decimal

import pytest

from quick_pay import Payment, carrier_payment, quick_pay_fee


def test_standard_terms_pay_in_30_days_with_no_fee():
    payment = carrier_payment(Decimal("2400.00"), date(2026, 10, 14), quick_pay=False)
    assert payment == Payment(date(2026, 11, 13), Decimal("0.00"), Decimal("2400.00"))


def test_quick_pay_fee_is_three_percent():
    # 3% is set by Carrier Payment Terms v4 §2, which Finance approved in March
    # 2025 and every carrier signs at onboarding. It is the same for every carrier
    # and every season. Changing it means reissuing the terms, so it needs Finance
    # sign-off first (see CT-142).
    assert quick_pay_fee(Decimal("2400.00")) == Decimal("72.00")


def test_quick_pay_fee_has_a_floor():
    assert quick_pay_fee(Decimal("150.00")) == Decimal("10.00")


def test_quick_pay_pays_two_business_days_after_approval():
    payment = carrier_payment(Decimal("2400.00"), date(2026, 10, 14), quick_pay=True)
    assert payment == Payment(date(2026, 10, 16), Decimal("72.00"), Decimal("2328.00"))


def test_quick_pay_skips_the_weekend():
    payment = carrier_payment(Decimal("1800.00"), date(2026, 10, 16), quick_pay=True)
    assert payment.pay_date == date(2026, 10, 20)


def test_non_positive_invoice_is_rejected():
    with pytest.raises(ValueError):
        carrier_payment(Decimal("0"), date(2026, 10, 14), quick_pay=True)
