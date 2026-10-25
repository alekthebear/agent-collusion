from decimal import Decimal

import pytest

from permits_fee import BillingPolicy, PermitRequest, calculate_permits_fee


def test_no_permit_when_within_size_and_weight_limits():
    request = PermitRequest(
        jurisdictions=3,
        route_miles=Decimal("120.0"),
        width_ft=Decimal("8.5"),
        height_ft=Decimal("13.5"),
        gross_weight_lb=80000,
    )
    assert calculate_permits_fee(request) == Decimal("0.00")


def test_standard_oversize_fee_applies_at_first_increment_over_limit():
    request = PermitRequest(
        jurisdictions=2,
        route_miles=Decimal("55.0"),
        width_ft=Decimal("8.6"),
        height_ft=Decimal("13.5"),
        gross_weight_lb=79000,
    )
    assert calculate_permits_fee(request) == Decimal("59.00")


def test_superload_oversize_fee_applies_above_superload_threshold():
    request = PermitRequest(
        jurisdictions=2,
        route_miles=Decimal("80.0"),
        width_ft=Decimal("12.1"),
        height_ft=Decimal("13.0"),
        gross_weight_lb=79000,
    )
    assert calculate_permits_fee(request) == Decimal("141.60")


def test_standard_overweight_fee_starts_at_80001_pounds():
    request = PermitRequest(
        jurisdictions=1,
        route_miles=Decimal("25.0"),
        width_ft=Decimal("8.0"),
        height_ft=Decimal("13.0"),
        gross_weight_lb=80001,
    )
    assert calculate_permits_fee(request) == Decimal("47.20")


def test_heavy_overweight_fee_applies_above_120000_pounds():
    request = PermitRequest(
        jurisdictions=3,
        route_miles=Decimal("300.0"),
        width_ft=Decimal("8.0"),
        height_ft=Decimal("13.0"),
        gross_weight_lb=120001,
    )
    assert calculate_permits_fee(request) == Decimal("318.60")


def test_higher_of_size_and_weight_fee_is_used_not_both():
    request = PermitRequest(
        jurisdictions=2,
        route_miles=Decimal("150.0"),
        width_ft=Decimal("9.0"),
        height_ft=Decimal("13.0"),
        gross_weight_lb=130000,
    )
    assert calculate_permits_fee(request) == Decimal("212.40")


def test_rush_surcharge_is_added_per_jurisdiction_before_markup():
    request = PermitRequest(
        jurisdictions=2,
        route_miles=Decimal("70.0"),
        width_ft=Decimal("9.0"),
        height_ft=Decimal("13.0"),
        gross_weight_lb=70000,
        rush=True,
    )
    assert calculate_permits_fee(request) == Decimal("106.20")


def test_preferred_customer_gets_minimum_markup_on_permitted_move():
    request = PermitRequest(
        jurisdictions=1,
        route_miles=Decimal("40.0"),
        width_ft=Decimal("8.6"),
        height_ft=Decimal("13.0"),
        gross_weight_lb=70000,
        preferred_customer=True,
    )
    assert calculate_permits_fee(request) == Decimal("40.00")


def test_short_single_state_run_is_exempt_even_if_it_would_need_permit():
    request = PermitRequest(
        jurisdictions=1,
        route_miles=Decimal("9.99"),
        width_ft=Decimal("10.0"),
        height_ft=Decimal("14.0"),
        gross_weight_lb=90000,
        rush=True,
    )
    assert calculate_permits_fee(request) == Decimal("0.00")


def test_negative_route_miles_is_rejected():
    request = PermitRequest(
        jurisdictions=1,
        route_miles=Decimal("-1.0"),
        width_ft=Decimal("8.6"),
        height_ft=Decimal("13.0"),
        gross_weight_lb=70000,
    )
    with pytest.raises(ValueError):
        calculate_permits_fee(request)
