from decimal import Decimal

import pytest

from driver_endorsement_check import (
    DriverEndorsements,
    LoadRequirements,
    evaluate_driver_endorsement_check,
)


def test_basic_non_hazmat_single_trailer_is_approved():
    result = evaluate_driver_endorsement_check(
        DriverEndorsements(),
        LoadRequirements(),
    )
    assert result.approved is True
    assert result.requires_hazmat is False
    assert result.requires_tanker is False
    assert result.requires_doubles is False
    assert result.risk_score == Decimal("0.00")


def test_placarded_hazmat_requires_hazmat_endorsement():
    result = evaluate_driver_endorsement_check(
        DriverEndorsements(),
        LoadRequirements(placarded_hazmat=True),
    )
    assert result.approved is False
    assert result.requires_hazmat is True
    assert result.risk_score == Decimal("0.55")
    assert result.reason == "missing hazmat endorsement"


def test_residue_only_empty_tank_does_not_require_hazmat():
    result = evaluate_driver_endorsement_check(
        DriverEndorsements(),
        LoadRequirements(placarded_hazmat=True, empty_tank=True, residue_only=True),
    )
    assert result.approved is True
    assert result.requires_hazmat is False
    assert result.risk_score == Decimal("0.00")


def test_tanker_required_only_above_1000_gallons():
    exact = evaluate_driver_endorsement_check(
        DriverEndorsements(),
        LoadRequirements(liquid_or_gas_bulk=True, tank_capacity_gallons=1000),
    )
    above = evaluate_driver_endorsement_check(
        DriverEndorsements(),
        LoadRequirements(liquid_or_gas_bulk=True, tank_capacity_gallons=1001),
    )
    assert exact.requires_tanker is False
    assert above.requires_tanker is True
    assert above.approved is False
    assert above.risk_score == Decimal("0.30")


def test_empty_non_residue_tank_does_not_require_tanker():
    result = evaluate_driver_endorsement_check(
        DriverEndorsements(),
        LoadRequirements(liquid_or_gas_bulk=True, tank_capacity_gallons=7000, empty_tank=True),
    )
    assert result.requires_tanker is False
    assert result.approved is True


def test_doubles_required_for_two_trailing_units():
    result = evaluate_driver_endorsement_check(
        DriverEndorsements(),
        LoadRequirements(trailing_units=2),
    )
    assert result.requires_doubles is True
    assert result.approved is False
    assert result.risk_score == Decimal("0.25")


def test_restricted_hazmat_fails_on_interstate_even_with_hazmat():
    result = evaluate_driver_endorsement_check(
        DriverEndorsements(hazmat=True, hazmat_restricted_intrastate=True),
        LoadRequirements(placarded_hazmat=True, crosses_state_lines=True),
    )
    assert result.approved is False
    assert result.risk_score == Decimal("0.20")
    assert result.reason == "restricted hazmat not valid interstate"


def test_twic_lowers_risk_for_qualified_port_hazmat_load():
    result = evaluate_driver_endorsement_check(
        DriverEndorsements(hazmat=True, twic=True),
        LoadRequirements(placarded_hazmat=True, is_port_pickup=True),
    )
    assert result.approved is True
    assert result.risk_score == Decimal("0.00")
    assert result.reason == "meets endorsement requirements"


def test_safety_hold_overrides_otherwise_qualified_driver():
    result = evaluate_driver_endorsement_check(
        DriverEndorsements(hazmat=True, tanker=True, doubles=True, safety_hold=True),
        LoadRequirements(placarded_hazmat=True, liquid_or_gas_bulk=True, tank_capacity_gallons=5000, trailing_units=2),
    )
    assert result.approved is False
    assert result.risk_score == Decimal("1.00")
    assert result.reason == "driver on safety hold"


def test_invalid_residue_without_empty_tank_is_rejected():
    with pytest.raises(ValueError):
        evaluate_driver_endorsement_check(
            DriverEndorsements(),
            LoadRequirements(residue_only=True),
        )
