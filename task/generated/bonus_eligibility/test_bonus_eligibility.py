from decimal import Decimal

import pytest

from bonus_eligibility import BonusMetrics, BonusRules, evaluate_bonus_eligibility


def test_linehaul_exact_thresholds_are_eligible():
    metrics = BonusMetrics(
        role="linehaul",
        gross_pay=Decimal("2500.00"),
        on_time_deliveries=98,
        total_deliveries=100,
        miles=9500,
    )
    decision = evaluate_bonus_eligibility(metrics)
    assert decision.eligible is True
    assert decision.amount == Decimal("100.00")
    assert decision.reason == "eligible"


def test_local_below_on_time_threshold_is_ineligible():
    metrics = BonusMetrics(
        role="local",
        gross_pay=Decimal("1800.00"),
        on_time_deliveries=95,
        total_deliveries=100,
        miles=5000,
    )
    decision = evaluate_bonus_eligibility(metrics)
    assert decision.eligible is False
    assert decision.amount == Decimal("0.00")
    assert decision.reason == "service"


def test_miles_below_threshold_fails_utilization():
    metrics = BonusMetrics(
        role="local",
        gross_pay=Decimal("1800.00"),
        on_time_deliveries=96,
        total_deliveries=100,
        miles=4199,
    )
    decision = evaluate_bonus_eligibility(metrics)
    assert decision.eligible is False
    assert decision.reason == "utilization"


def test_preventable_accident_is_hard_disqualifier_even_with_leave():
    metrics = BonusMetrics(
        role="linehaul",
        gross_pay=Decimal("3000.00"),
        on_time_deliveries=50,
        total_deliveries=100,
        miles=1000,
        preventable_accidents=1,
        protected_leave=True,
    )
    decision = evaluate_bonus_eligibility(metrics)
    assert decision.eligible is False
    assert decision.reason == "preventable accident"


def test_two_moving_violations_disqualify_at_boundary():
    metrics = BonusMetrics(
        role="local",
        gross_pay=Decimal("1900.00"),
        on_time_deliveries=100,
        total_deliveries=100,
        miles=5000,
        moving_violations=2,
    )
    decision = evaluate_bonus_eligibility(metrics)
    assert decision.eligible is False
    assert decision.reason == "moving violations"


def test_three_tardies_count_as_one_absence_and_still_passes():
    metrics = BonusMetrics(
        role="local",
        gross_pay=Decimal("2000.00"),
        on_time_deliveries=96,
        total_deliveries=100,
        miles=4200,
        tardies=3,
    )
    decision = evaluate_bonus_eligibility(metrics)
    assert decision.eligible is True
    assert decision.amount == Decimal("60.00")


def test_attendance_fails_when_absences_plus_tardy_conversion_exceed_limit():
    metrics = BonusMetrics(
        role="linehaul",
        gross_pay=Decimal("2200.00"),
        on_time_deliveries=99,
        total_deliveries=100,
        miles=10000,
        unexcused_absences=1,
        tardies=3,
    )
    decision = evaluate_bonus_eligibility(metrics)
    assert decision.eligible is False
    assert decision.reason == "attendance"


def test_protected_leave_waives_service_utilization_and_attendance():
    metrics = BonusMetrics(
        role="linehaul",
        gross_pay=Decimal("2100.00"),
        on_time_deliveries=0,
        total_deliveries=10,
        miles=0,
        unexcused_absences=5,
        tardies=8,
        protected_leave=True,
    )
    decision = evaluate_bonus_eligibility(metrics)
    assert decision.eligible is True
    assert decision.amount == Decimal("84.00")


def test_final_warning_halves_bonus_and_rounds_half_up():
    metrics = BonusMetrics(
        role="local",
        gross_pay=Decimal("3333.00"),
        on_time_deliveries=96,
        total_deliveries=100,
        miles=4200,
        final_warning=True,
    )
    decision = evaluate_bonus_eligibility(metrics)
    assert decision.eligible is True
    assert decision.amount == Decimal("50.00")


def test_on_time_deliveries_cannot_exceed_total():
    metrics = BonusMetrics(
        role="local",
        gross_pay=Decimal("1000.00"),
        on_time_deliveries=11,
        total_deliveries=10,
        miles=5000,
    )
    with pytest.raises(ValueError):
        evaluate_bonus_eligibility(metrics)
