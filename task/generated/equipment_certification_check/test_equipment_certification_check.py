from datetime import date
from decimal import Decimal

import pytest

from equipment_certification_check import (
    EquipmentCertification,
    LoadCertificationRequirement,
    evaluate_equipment_certification_check,
)


def day(d):
    return date(2026, 4, d)


def test_case_and_whitespace_normalize_for_type_match():
    requirement = LoadCertificationRequirement(required_type="  FOOD GRADE  ", pickup_date=day(10))
    certs = [
        EquipmentCertification(
            certification_type="food-grade",
            effective_date=day(1),
            expiration_date=day(30),
            score=Decimal("85.0"),
        )
    ]
    assert evaluate_equipment_certification_check(requirement, certs) is True


def test_food_grade_synonym_and_half_up_rounding_meet_threshold():
    requirement = LoadCertificationRequirement(required_type="food-grade", pickup_date=day(10))
    certs = [
        EquipmentCertification(
            certification_type="food grade",
            effective_date=day(1),
            expiration_date=day(10),
            score=Decimal("84.95"),
        )
    ]
    assert evaluate_equipment_certification_check(requirement, certs) is True


def test_food_grade_below_threshold_fails_after_rounding():
    requirement = LoadCertificationRequirement(required_type="food-grade", pickup_date=day(10))
    certs = [
        EquipmentCertification(
            certification_type="food-grade",
            effective_date=day(1),
            expiration_date=day(20),
            score=Decimal("84.94"),
        )
    ]
    assert evaluate_equipment_certification_check(requirement, certs) is False


def test_liftgate_missing_score_is_accepted():
    requirement = LoadCertificationRequirement(required_type="lift gate", pickup_date=day(10))
    certs = [
        EquipmentCertification(
            certification_type="lift-gate",
            effective_date=day(5),
            expiration_date=day(12),
            score=None,
        )
    ]
    assert evaluate_equipment_certification_check(requirement, certs) is True


def test_liftgate_with_score_below_threshold_fails():
    requirement = LoadCertificationRequirement(required_type="liftgate", pickup_date=day(10))
    certs = [
        EquipmentCertification(
            certification_type="liftgate",
            effective_date=day(1),
            expiration_date=day(15),
            score=Decimal("69.9"),
        )
    ]
    assert evaluate_equipment_certification_check(requirement, certs) is False


def test_air_ride_ignores_score_thresholds():
    requirement = LoadCertificationRequirement(required_type="air ride", pickup_date=day(10))
    certs = [
        EquipmentCertification(
            certification_type="air-ride",
            effective_date=day(10),
            expiration_date=None,
            score=Decimal("10.0"),
        )
    ]
    assert evaluate_equipment_certification_check(requirement, certs) is True


def test_effective_date_after_pickup_is_not_yet_valid():
    requirement = LoadCertificationRequirement(required_type="air-ride", pickup_date=day(10))
    certs = [
        EquipmentCertification(
            certification_type="air-ride",
            effective_date=day(11),
            expiration_date=None,
        )
    ]
    assert evaluate_equipment_certification_check(requirement, certs) is False


def test_expiration_on_pickup_date_is_still_valid():
    requirement = LoadCertificationRequirement(required_type="liftgate", pickup_date=day(10))
    certs = [
        EquipmentCertification(
            certification_type="liftgate",
            effective_date=day(1),
            expiration_date=day(10),
            score=Decimal("70.0"),
        )
    ]
    assert evaluate_equipment_certification_check(requirement, certs) is True


def test_revoked_on_pickup_date_is_invalid_even_before_expiration():
    requirement = LoadCertificationRequirement(required_type="food-grade", pickup_date=day(10))
    certs = [
        EquipmentCertification(
            certification_type="food-grade",
            effective_date=day(1),
            expiration_date=day(30),
            revoked_date=day(10),
            score=Decimal("90.0"),
        )
    ]
    assert evaluate_equipment_certification_check(requirement, certs) is False


def test_any_matching_active_certification_can_satisfy_requirement():
    requirement = LoadCertificationRequirement(required_type="food-grade", pickup_date=day(10))
    certs = [
        EquipmentCertification(
            certification_type="food-grade",
            effective_date=day(1),
            expiration_date=day(9),
            score=Decimal("99.0"),
        ),
        EquipmentCertification(
            certification_type="food-grade",
            effective_date=day(1),
            expiration_date=day(20),
            score=Decimal("85.0"),
        ),
    ]
    assert evaluate_equipment_certification_check(requirement, certs) is True


def test_blank_required_type_is_rejected():
    with pytest.raises(ValueError):
        evaluate_equipment_certification_check(
            LoadCertificationRequirement(required_type="   ", pickup_date=day(10)),
            [],
        )
