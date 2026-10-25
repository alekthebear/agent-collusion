from datetime import date, timedelta
from decimal import Decimal

import pytest

from safety_score_gate import (
    CarrierSafetySnapshot,
    SafetyGateConfig,
    evaluate_safety_score_gate,
)


AS_OF = date(2026, 4, 1)


def snapshot(**overrides):
    base = dict(
        dot_score=Decimal("64.9"),
        has_active_intervention=False,
        insurance_on_file_date=AS_OF - timedelta(days=20),
        authority_granted_date=AS_OF - timedelta(days=400),
        consecutive_clean_months=8,
        fatal_crashes_last_24m=0,
        out_of_service_rate=Decimal("20.0"),
    )
    base.update(overrides)
    return CarrierSafetySnapshot(**base)


def test_score_at_threshold_passes():
    result = evaluate_safety_score_gate(snapshot(dot_score=Decimal("65.0")), AS_OF)
    assert result.passed is True
    assert result.violations == ()


def test_score_rounds_half_up_before_comparison():
    result = evaluate_safety_score_gate(snapshot(dot_score=Decimal("65.04")), AS_OF)
    assert result.passed is True
    assert result.violations == ()


def test_score_above_threshold_without_grace_fails():
    result = evaluate_safety_score_gate(
        snapshot(dot_score=Decimal("65.06"), consecutive_clean_months=5),
        AS_OF,
    )
    assert result.passed is False
    assert result.violations == ("dot_score",)


def test_grace_band_allows_small_overage_with_enough_clean_months():
    result = evaluate_safety_score_gate(
        snapshot(dot_score=Decimal("67.0"), consecutive_clean_months=6),
        AS_OF,
    )
    assert result.passed is True
    assert result.violations == ()


def test_active_intervention_blocks_even_if_otherwise_qualified():
    result = evaluate_safety_score_gate(snapshot(has_active_intervention=True), AS_OF)
    assert result.passed is False
    assert result.violations == ("active_intervention",)


def test_missing_score_new_entrant_inside_age_window_passes():
    result = evaluate_safety_score_gate(
        snapshot(dot_score=None, authority_granted_date=AS_OF - timedelta(days=180)),
        AS_OF,
    )
    assert result.passed is True
    assert result.violations == ()


def test_missing_score_old_carrier_fails():
    result = evaluate_safety_score_gate(snapshot(dot_score=None), AS_OF)
    assert result.passed is False
    assert result.violations == ("missing_score",)


def test_insurance_becomes_stale_only_after_limit():
    fresh = evaluate_safety_score_gate(
        snapshot(insurance_on_file_date=AS_OF - timedelta(days=45)),
        AS_OF,
    )
    stale = evaluate_safety_score_gate(
        snapshot(insurance_on_file_date=AS_OF - timedelta(days=46)),
        AS_OF,
    )
    assert fresh.passed is True
    assert stale.passed is False
    assert stale.violations == ("stale_insurance",)


def test_fatal_crash_and_oos_rate_both_reported():
    result = evaluate_safety_score_gate(
        snapshot(fatal_crashes_last_24m=1, out_of_service_rate=Decimal("38.1")),
        AS_OF,
    )
    assert result.passed is False
    assert result.violations == ("fatal_crash_history", "out_of_service_rate")


def test_negative_score_is_rejected():
    with pytest.raises(ValueError):
        evaluate_safety_score_gate(snapshot(dot_score=Decimal("-1.0")), AS_OF)
