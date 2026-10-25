from decimal import Decimal

import pytest

from oversize_compliance_check import ComplianceResult, LoadProfile, evaluate_oversize_compliance_check


def test_base_legal_load_is_compliant_without_flags():
    load = LoadProfile(
        width_in=102,
        height_in=162,
        length_ft=Decimal("53"),
        gross_weight_lb=80000,
        jurisdiction="OK",
    )
    assert evaluate_oversize_compliance_check(load) == ComplianceResult(True, False, False, 0, None)


def test_width_one_inch_over_legal_needs_permit_only():
    load = LoadProfile(
        width_in=103,
        height_in=162,
        length_ft=Decimal("53"),
        gross_weight_lb=80000,
        jurisdiction="OK",
    )
    assert evaluate_oversize_compliance_check(load) == ComplianceResult(True, True, False, 0, None)


def test_width_over_twelve_feet_requires_one_escort():
    load = LoadProfile(
        width_in=145,
        height_in=162,
        length_ft=Decimal("53"),
        gross_weight_lb=80000,
        jurisdiction="OK",
    )
    result = evaluate_oversize_compliance_check(load)
    assert result.escort_count == 1
    assert result.needs_permit is True
    assert result.compliant is True


def test_width_over_fourteen_feet_requires_two_escorts():
    load = LoadProfile(
        width_in=169,
        height_in=162,
        length_ft=Decimal("53"),
        gross_weight_lb=80000,
        jurisdiction="OK",
    )
    assert evaluate_oversize_compliance_check(load).escort_count == 2


def test_texas_height_limit_allows_fourteen_feet_without_flags():
    load = LoadProfile(
        width_in=102,
        height_in=168,
        length_ft=Decimal("53"),
        gross_weight_lb=80000,
        jurisdiction="TX",
    )
    assert evaluate_oversize_compliance_check(load) == ComplianceResult(True, False, False, 0, None)


def test_height_more_than_twelve_inches_over_limit_is_rejected():
    load = LoadProfile(
        width_in=102,
        height_in=175,
        length_ft=Decimal("53"),
        gross_weight_lb=80000,
        jurisdiction="OK",
    )
    assert evaluate_oversize_compliance_check(load) == ComplianceResult(
        False, True, True, 0, "height exceeds auto-routing tolerance"
    )


def test_florida_shorter_length_limit_triggers_permit():
    load = LoadProfile(
        width_in=102,
        height_in=162,
        length_ft=Decimal("49"),
        gross_weight_lb=80000,
        jurisdiction="FL",
    )
    result = evaluate_oversize_compliance_check(load)
    assert result.needs_permit is True
    assert result.compliant is True
    assert result.escort_count == 0


def test_non_divisible_overweight_load_is_rejected():
    load = LoadProfile(
        width_in=102,
        height_in=162,
        length_ft=Decimal("53"),
        gross_weight_lb=80001,
        jurisdiction="OK",
        divisible_load=False,
    )
    assert evaluate_oversize_compliance_check(load) == ComplianceResult(
        False, True, False, 0, "non-divisible overweight load"
    )


def test_nevada_weight_limit_allows_heavy_divisible_load():
    load = LoadProfile(
        width_in=102,
        height_in=162,
        length_ft=Decimal("53"),
        gross_weight_lb=129000,
        jurisdiction="NV",
    )
    assert evaluate_oversize_compliance_check(load) == ComplianceResult(True, False, False, 0, None)


def test_hazmat_width_over_twelve_feet_is_rejected():
    load = LoadProfile(
        width_in=145,
        height_in=162,
        length_ft=Decimal("53"),
        gross_weight_lb=80000,
        jurisdiction="OK",
        hazmat=True,
    )
    assert evaluate_oversize_compliance_check(load) == ComplianceResult(
        False, True, False, 1, "hazmat exceeds corridor allowance"
    )
