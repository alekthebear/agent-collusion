from decimal import Decimal

import pytest

from linehaul_rate_per_mile import (
    ContractTerms,
    LinehaulRequest,
    calculate_linehaul_rate_per_mile,
)


def test_under_250_miles_uses_short_band_rate():
    req = LinehaulRequest(paid_miles=200)
    assert calculate_linehaul_rate_per_mile(req) == Decimal("2.45")


def test_250_miles_moves_to_middle_band_and_no_team_premium_at_boundary():
    req = LinehaulRequest(paid_miles=250, team_service=True)
    assert calculate_linehaul_rate_per_mile(req) == Decimal("2.20")


def test_short_haul_surcharge_applies_below_75_miles():
    req = LinehaulRequest(paid_miles=74)
    assert calculate_linehaul_rate_per_mile(req) == Decimal("4.40")


def test_hazmat_is_skipped_under_50_miles():
    req = LinehaulRequest(paid_miles=49, hazmat=True)
    assert calculate_linehaul_rate_per_mile(req) == Decimal("6.64")


def test_hazmat_applies_at_50_miles_and_rounds_up_to_protect_minimum():
    req = LinehaulRequest(paid_miles=50, hazmat=True)
    assert calculate_linehaul_rate_per_mile(req) == Decimal("6.50")


def test_team_service_applies_only_over_250_miles():
    req = LinehaulRequest(paid_miles=251, team_service=True)
    assert calculate_linehaul_rate_per_mile(req) == Decimal("2.42")


def test_long_haul_discount_applies_at_1000_miles():
    req = LinehaulRequest(paid_miles=1000)
    assert calculate_linehaul_rate_per_mile(req) == Decimal("1.93")


def test_multiple_premiums_stack_when_eligible():
    req = LinehaulRequest(paid_miles=300, hazmat=True, team_service=True, overweight_permit=True)
    assert calculate_linehaul_rate_per_mile(req) == Decimal("2.70")


def test_invalid_nonpositive_miles_are_rejected():
    with pytest.raises(ValueError):
        calculate_linehaul_rate_per_mile(LinehaulRequest(paid_miles=0))
