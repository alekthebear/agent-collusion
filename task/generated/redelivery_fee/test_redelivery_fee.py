from decimal import Decimal

import pytest

from redelivery_fee import RedeliveryRequest, RedeliveryTariff, calculate_redelivery_fee


def test_carrier_fault_reason_is_not_billable():
    request = RedeliveryRequest(failed_reason="carrier_missed_appt", retraced_miles=Decimal("22"))
    assert calculate_redelivery_fee(request) == Decimal("0.00")


def test_unknown_reason_is_not_billable():
    request = RedeliveryRequest(failed_reason="security_hold", retraced_miles=Decimal("18"))
    assert calculate_redelivery_fee(request) == Decimal("0.00")


def test_below_threshold_bills_minimum_only():
    request = RedeliveryRequest(failed_reason="closed", retraced_miles=Decimal("9.99"))
    assert calculate_redelivery_fee(request) == Decimal("85.00")


def test_threshold_miles_start_mileage_charge():
    request = RedeliveryRequest(failed_reason="closed", retraced_miles=Decimal("10"))
    assert calculate_redelivery_fee(request) == Decimal("127.50")


def test_rural_uses_higher_per_mile_rate():
    request = RedeliveryRequest(failed_reason="refused", retraced_miles=Decimal("12"), is_rural=True)
    assert calculate_redelivery_fee(request) == Decimal("146.20")


def test_residential_first_failure_is_halved_but_not_below_minimum():
    request = RedeliveryRequest(failed_reason="bad_address", retraced_miles=Decimal("8"), is_residential=True)
    assert calculate_redelivery_fee(request) == Decimal("55.00")


def test_second_failure_adds_surcharge_and_no_residential_discount():
    request = RedeliveryRequest(
        failed_reason="no_dock",
        retraced_miles=Decimal("10"),
        is_residential=True,
        customer_fault_count=2,
    )
    assert calculate_redelivery_fee(request) == Decimal("162.50")


def test_no_one_available_without_kept_appointment_is_not_billable():
    request = RedeliveryRequest(
        failed_reason="no_one_available",
        retraced_miles=Decimal("15"),
        appointment_kept=False,
    )
    assert calculate_redelivery_fee(request) == Decimal("0.00")


def test_negative_miles_are_rejected():
    with pytest.raises(ValueError):
        calculate_redelivery_fee(RedeliveryRequest(failed_reason="closed", retraced_miles=Decimal("-1")))


def test_custom_tariff_rounds_half_up_to_cents():
    tariff = RedeliveryTariff(minimum_fee=Decimal("80.00"), per_mile_rate=Decimal("4.333"))
    request = RedeliveryRequest(failed_reason="closed", retraced_miles=Decimal("10.5"))
    assert calculate_redelivery_fee(request, tariff) == Decimal("125.50")
