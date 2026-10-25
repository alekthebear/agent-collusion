from datetime import date
from decimal import Decimal

import pytest

from carrier_authority_age_check import (
    AuthorityAgePolicy,
    CarrierAuthorityFacts,
    evaluate_carrier_authority_age_check,
)


def on(month, day):
    return date(2026, month, day)


def test_meets_minimum_age_at_exact_boundary():
    facts = CarrierAuthorityFacts(
        authority_granted_on=on(1, 1),
        reference_date=on(4, 1),
        out_of_service_rate=Decimal("9.99"),
    )
    decision = evaluate_carrier_authority_age_check(facts)
    assert decision.approved is True
    assert decision.used_waiver is False
    assert decision.authority_age_days == 90
    assert decision.reason == "meets_minimum_age"


def test_below_minimum_but_meets_waiver_rules_is_approved():
    facts = CarrierAuthorityFacts(
        authority_granted_on=on(1, 31),
        reference_date=on(4, 1),
        out_of_service_rate=Decimal("5.00"),
    )
    decision = evaluate_carrier_authority_age_check(facts)
    assert decision.approved is True
    assert decision.used_waiver is True
    assert decision.authority_age_days == 60
    assert decision.reason == "approved_by_waiver"


def test_below_waiver_minimum_fails_even_when_waivers_allowed():
    facts = CarrierAuthorityFacts(
        authority_granted_on=on(2, 1),
        reference_date=on(4, 1),
        out_of_service_rate=Decimal("1.00"),
    )
    decision = evaluate_carrier_authority_age_check(facts)
    assert decision.approved is False
    assert decision.used_waiver is False
    assert decision.authority_age_days == 59
    assert decision.reason == "below_waiver_minimum"


def test_waiver_can_be_disabled():
    facts = CarrierAuthorityFacts(
        authority_granted_on=on(1, 31),
        reference_date=on(4, 1),
        out_of_service_rate=Decimal("1.00"),
    )
    policy = AuthorityAgePolicy(allow_waiver=False)
    decision = evaluate_carrier_authority_age_check(facts, policy)
    assert decision.approved is False
    assert decision.reason == "below_minimum_age"


def test_any_insurance_lapse_blocks_waiver():
    facts = CarrierAuthorityFacts(
        authority_granted_on=on(1, 31),
        reference_date=on(4, 1),
        out_of_service_rate=Decimal("1.00"),
        insurance_lapse_days_last_12_months=1,
    )
    decision = evaluate_carrier_authority_age_check(facts)
    assert decision.approved is False
    assert decision.reason == "recent_insurance_lapse"


def test_rate_is_rounded_half_up_before_standard_limit_comparison():
    facts = CarrierAuthorityFacts(
        authority_granted_on=on(1, 31),
        reference_date=on(4, 1),
        out_of_service_rate=Decimal("5.005"),
    )
    decision = evaluate_carrier_authority_age_check(facts)
    assert decision.approved is False
    assert decision.rounded_out_of_service_rate == Decimal("5.01")
    assert decision.reason == "out_of_service_rate_too_high"


def test_hazmat_uses_stricter_rate_limit():
    facts = CarrierAuthorityFacts(
        authority_granted_on=on(1, 31),
        reference_date=on(4, 1),
        out_of_service_rate=Decimal("3.01"),
        hazmat_load=True,
    )
    decision = evaluate_carrier_authority_age_check(facts)
    assert decision.approved is False
    assert decision.reason == "out_of_service_rate_too_high"


def test_hazmat_safety_alert_blocks_otherwise_eligible_waiver():
    facts = CarrierAuthorityFacts(
        authority_granted_on=on(1, 31),
        reference_date=on(4, 1),
        out_of_service_rate=Decimal("2.50"),
        hazmat_load=True,
        safety_alert=True,
    )
    decision = evaluate_carrier_authority_age_check(facts)
    assert decision.approved is False
    assert decision.reason == "hazmat_safety_alert"


def test_revoked_authority_always_fails():
    facts = CarrierAuthorityFacts(
        authority_granted_on=on(1, 1),
        reference_date=on(4, 5),
        out_of_service_rate=Decimal("0.00"),
        revoked=True,
    )
    decision = evaluate_carrier_authority_age_check(facts)
    assert decision.approved is False
    assert decision.reason == "authority_revoked"


def test_grant_date_after_reference_date_is_rejected():
    facts = CarrierAuthorityFacts(
        authority_granted_on=on(4, 2),
        reference_date=on(4, 1),
        out_of_service_rate=Decimal("0.00"),
    )
    with pytest.raises(ValueError):
        evaluate_carrier_authority_age_check(facts)
