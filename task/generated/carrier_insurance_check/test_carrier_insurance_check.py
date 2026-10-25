from datetime import date
from decimal import Decimal

import pytest

from carrier_insurance_check import (
    CarrierPolicySet,
    Coverage,
    InsuranceRequirements,
    LoadFacts,
    evaluate_carrier_insurance_check,
)


def d(day):
    return date(2026, 5, day)


def base_policies():
    return CarrierPolicySet(
        liability=Coverage(limit=Decimal("1000000.00"), expires_on=d(31)),
        cargo=Coverage(limit=Decimal("100000.00"), expires_on=d(31)),
        trailer_interchange=Coverage(limit=Decimal("35000.00"), expires_on=d(31)),
    )


def test_standard_load_with_all_required_coverages_passes():
    result = evaluate_carrier_insurance_check(
        base_policies(),
        LoadFacts(shipment_value=Decimal("50000")),
        as_of=d(15),
    )
    assert result.compliant is True
    assert result.reasons == ()


def test_documents_move_waives_cargo_requirement():
    policies = CarrierPolicySet(
        liability=Coverage(limit=Decimal("1000000.00"), expires_on=d(31)),
        cargo=None,
    )
    result = evaluate_carrier_insurance_check(
        policies,
        LoadFacts(shipment_value=Decimal("10000"), mode="documents"),
        requirements=InsuranceRequirements(minimum_cargo=Decimal("100000")),
        as_of=d(15),
    )
    assert result.compliant is True
    assert result.cargo_ok is True


def test_low_value_load_under_2500_waives_cargo_requirement():
    policies = CarrierPolicySet(
        liability=Coverage(limit=Decimal("1000000.00"), expires_on=d(31)),
        cargo=None,
    )
    result = evaluate_carrier_insurance_check(
        policies,
        LoadFacts(shipment_value=Decimal("2499.99")),
        requirements=InsuranceRequirements(minimum_cargo=Decimal("0")),
        as_of=d(15),
    )
    assert result.compliant is True
    assert result.cargo_ok is True


def test_refrigerated_load_requires_at_least_100000_cargo():
    policies = CarrierPolicySet(
        liability=Coverage(limit=Decimal("1000000.00"), expires_on=d(31)),
        cargo=Coverage(limit=Decimal("99999.99"), expires_on=d(31)),
    )
    result = evaluate_carrier_insurance_check(
        policies,
        LoadFacts(shipment_value=Decimal("40000"), mode="refrigerated"),
        requirements=InsuranceRequirements(minimum_cargo=Decimal("0")),
        as_of=d(15),
    )
    assert result.compliant is False
    assert result.cargo_ok is False
    assert result.reasons == ("cargo below required 100000",)


def test_hazmat_requires_one_million_liability_even_if_customer_minimum_is_lower():
    policies = CarrierPolicySet(
        liability=Coverage(limit=Decimal("999999.99"), expires_on=d(31)),
        cargo=Coverage(limit=Decimal("100000.00"), expires_on=d(31)),
    )
    result = evaluate_carrier_insurance_check(
        policies,
        LoadFacts(shipment_value=Decimal("10000"), is_hazmat=True),
        requirements=InsuranceRequirements(minimum_liability=Decimal("750000")),
        as_of=d(15),
    )
    assert result.liability_ok is False
    assert result.reasons == ("liability below required 1000000",)


def test_nyc_move_requires_two_million_liability():
    policies = CarrierPolicySet(
        liability=Coverage(limit=Decimal("1999999.99"), expires_on=d(31)),
        cargo=Coverage(limit=Decimal("100000.00"), expires_on=d(31)),
    )
    result = evaluate_carrier_insurance_check(
        policies,
        LoadFacts(shipment_value=Decimal("15000"), origin_city="Queens"),
        as_of=d(15),
    )
    assert result.compliant is False
    assert result.reasons == ("liability below required 2000000",)


def test_trailer_interchange_required_when_using_customer_trailer():
    policies = CarrierPolicySet(
        liability=Coverage(limit=Decimal("1000000.00"), expires_on=d(31)),
        cargo=Coverage(limit=Decimal("100000.00"), expires_on=d(31)),
        trailer_interchange=None,
    )
    result = evaluate_carrier_insurance_check(
        policies,
        LoadFacts(shipment_value=Decimal("12000"), uses_customer_trailer=True),
        as_of=d(15),
    )
    assert result.trailer_interchange_ok is False
    assert result.reasons == ("trailer interchange missing or expired",)


def test_expiration_date_is_inclusive_through_listed_day():
    policies = CarrierPolicySet(
        liability=Coverage(limit=Decimal("1000000.00"), expires_on=d(15)),
        cargo=Coverage(limit=Decimal("100000.00"), expires_on=d(15)),
    )
    result = evaluate_carrier_insurance_check(
        policies,
        LoadFacts(shipment_value=Decimal("10000")),
        as_of=d(15),
    )
    assert result.compliant is True


def test_negative_shipment_value_is_rejected():
    with pytest.raises(ValueError):
        evaluate_carrier_insurance_check(
            base_policies(),
            LoadFacts(shipment_value=Decimal("-1.00")),
            as_of=d(15),
        )
