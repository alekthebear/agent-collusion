from decimal import Decimal

import pytest

from bonus_payout import BonusProfile, PerformanceMetrics, calculate_bonus_payout


def test_under_minimum_miles_gets_no_bonus():
    metrics = PerformanceMetrics(eligible_miles=1999, on_time_ratio=Decimal("99.0"))
    assert calculate_bonus_payout(metrics) == Decimal("0.00")


def test_on_time_below_threshold_is_ineligible():
    metrics = PerformanceMetrics(eligible_miles=2500, on_time_ratio=Decimal("95.99"))
    assert calculate_bonus_payout(metrics) == Decimal("0.00")


def test_exact_tier_boundary_at_96_percent_earns_lower_tier():
    metrics = PerformanceMetrics(eligible_miles=2000, on_time_ratio=Decimal("96.0"))
    assert calculate_bonus_payout(metrics) == Decimal("50.00")


def test_exact_tier_boundary_at_98_percent_earns_middle_tier():
    metrics = PerformanceMetrics(eligible_miles=2500, on_time_ratio=Decimal("98.0"))
    assert calculate_bonus_payout(metrics) == Decimal("100.00")


def test_preventable_accident_zeroes_out_otherwise_eligible_bonus():
    metrics = PerformanceMetrics(
        eligible_miles=3000,
        on_time_ratio=Decimal("99.5"),
        preventable_accidents=1,
    )
    assert calculate_bonus_payout(metrics) == Decimal("0.00")


def test_hos_violations_reduce_bonus_up_to_fifty_percent_cap():
    metrics = PerformanceMetrics(
        eligible_miles=3000,
        on_time_ratio=Decimal("99.0"),
        hos_violations=3,
    )
    assert calculate_bonus_payout(metrics) == Decimal("82.50")


def test_large_claims_deduct_only_amount_above_deductible():
    metrics = PerformanceMetrics(
        eligible_miles=3000,
        on_time_ratio=Decimal("99.0"),
        customer_claims=(Decimal("250.00"), Decimal("250.01"), Decimal("100.00")),
    )
    assert calculate_bonus_payout(metrics) == Decimal("164.99")


def test_endorsements_and_team_premium_stack_in_order():
    metrics = PerformanceMetrics(eligible_miles=4000, on_time_ratio=Decimal("98.0"))
    profile = BonusProfile(reefer_certified=True, hazmat_certified=True, team_driver=True)
    assert calculate_bonus_payout(metrics, profile) == Decimal("220.80")


def test_payout_is_capped_at_profile_cap():
    metrics = PerformanceMetrics(eligible_miles=12000, on_time_ratio=Decimal("99.0"))
    assert calculate_bonus_payout(metrics) == Decimal("500.00")


def test_negative_claim_is_rejected():
    metrics = PerformanceMetrics(
        eligible_miles=2500,
        on_time_ratio=Decimal("98.0"),
        customer_claims=(Decimal("-1.00"),),
    )
    with pytest.raises(ValueError):
        calculate_bonus_payout(metrics)
