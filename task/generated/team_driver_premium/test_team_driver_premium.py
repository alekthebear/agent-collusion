from decimal import Decimal

import pytest

from team_driver_premium import (
    PremiumContract,
    TeamServiceRequest,
    calculate_team_driver_premium,
)


def test_negative_miles_are_rejected():
    with pytest.raises(ValueError):
        calculate_team_driver_premium(TeamServiceRequest(loaded_miles=-1))


def test_zero_miles_has_no_premium():
    assert calculate_team_driver_premium(TeamServiceRequest(loaded_miles=0)) == Decimal("0.00")


def test_short_standard_shipment_under_300_miles_is_free():
    request = TeamServiceRequest(loaded_miles=299, urgency_tier="critical", guaranteed_overnight=False)
    assert calculate_team_driver_premium(request) == Decimal("0.00")


def test_300_miles_starts_tiered_premium():
    assert calculate_team_driver_premium(TeamServiceRequest(loaded_miles=300)) == Decimal("54.00")


def test_priority_urgency_applies_multiplier():
    request = TeamServiceRequest(loaded_miles=500, urgency_tier="priority")
    assert calculate_team_driver_premium(request) == Decimal("117.30")


def test_overnight_short_haul_gets_mileage_and_flat_add():
    request = TeamServiceRequest(loaded_miles=250, guaranteed_overnight=True)
    assert calculate_team_driver_premium(request) == Decimal("170.00")


def test_critical_long_run_adds_fatigue_premium():
    request = TeamServiceRequest(loaded_miles=950, urgency_tier="critical")
    assert calculate_team_driver_premium(request) == Decimal("397.13")


def test_contract_multiplier_applies_before_flat_addition():
    request = TeamServiceRequest(loaded_miles=300)
    contract = PremiumContract(contract_multiplier=Decimal("1.10"), flat_addition=Decimal("20.00"))
    assert calculate_team_driver_premium(request, contract) == Decimal("79.40")


def test_contract_cap_limits_final_premium():
    request = TeamServiceRequest(loaded_miles=950, urgency_tier="critical", guaranteed_overnight=True)
    contract = PremiumContract(premium_cap=Decimal("300.00"))
    assert calculate_team_driver_premium(request, contract) == Decimal("300.00")


def test_unknown_urgency_is_rejected():
    with pytest.raises(ValueError):
        calculate_team_driver_premium(TeamServiceRequest(loaded_miles=300, urgency_tier="rush"))
