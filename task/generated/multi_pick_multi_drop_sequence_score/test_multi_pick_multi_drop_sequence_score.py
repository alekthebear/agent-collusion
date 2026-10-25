from decimal import Decimal

import pytest

from multi_pick_multi_drop_sequence_score import (
    SequencePlan,
    SequenceStop,
    calculate_multi_pick_multi_drop_sequence_score,
)


def stop(window, dwell, appointment=False, congestion=False):
    return SequenceStop(
        window_minutes=window,
        expected_dwell_minutes=dwell,
        appointment_required=appointment,
        known_congestion=congestion,
    )


def test_first_15_backtrack_miles_are_free():
    plan = SequencePlan(
        pickup_count=1,
        delivery_count=1,
        direct_miles=Decimal("500"),
        planned_miles=Decimal("515"),
        stops=(stop(120, 30), stop(120, 30)),
    )
    assert calculate_multi_pick_multi_drop_sequence_score(plan) == Decimal("0.0")


def test_backtracking_uses_two_penalty_bands():
    plan = SequencePlan(
        pickup_count=1,
        delivery_count=1,
        direct_miles=Decimal("500"),
        planned_miles=Decimal("640"),
        stops=(stop(120, 30), stop(120, 30)),
    )
    assert calculate_multi_pick_multi_drop_sequence_score(plan) == Decimal("165.0")


def test_tight_window_and_appointment_points_stack():
    plan = SequencePlan(
        pickup_count=1,
        delivery_count=1,
        direct_miles=Decimal("100"),
        planned_miles=Decimal("100"),
        stops=(stop(59, 0, appointment=True), stop(180, 0)),
    )
    assert calculate_multi_pick_multi_drop_sequence_score(plan) == Decimal("15.0")


def test_all_wide_windows_receive_flexibility_credit():
    plan = SequencePlan(
        pickup_count=1,
        delivery_count=1,
        direct_miles=Decimal("100"),
        planned_miles=Decimal("100"),
        stops=(stop(180, 0), stop(240, 0)),
    )
    assert calculate_multi_pick_multi_drop_sequence_score(plan) == Decimal("0.0")


def test_common_two_by_two_pattern_gets_efficiency_credit():
    plan = SequencePlan(
        pickup_count=2,
        delivery_count=2,
        direct_miles=Decimal("250"),
        planned_miles=Decimal("250"),
        stops=(stop(120, 0), stop(120, 0), stop(120, 0), stop(120, 0)),
    )
    assert calculate_multi_pick_multi_drop_sequence_score(plan) == Decimal("5.0")


def test_hazmat_and_refrigerated_add_combined_compliance_bump():
    plan = SequencePlan(
        pickup_count=1,
        delivery_count=1,
        direct_miles=Decimal("100"),
        planned_miles=Decimal("100"),
        stops=(stop(120, 0), stop(120, 0)),
        hazmat=True,
        refrigerated=True,
    )
    assert calculate_multi_pick_multi_drop_sequence_score(plan) == Decimal("27.0")


def test_detention_risk_uses_thresholds_and_congestion_flag():
    plan = SequencePlan(
        pickup_count=1,
        delivery_count=1,
        direct_miles=Decimal("100"),
        planned_miles=Decimal("100"),
        stops=(stop(120, 100, congestion=True), stop(120, 50)),
    )
    assert calculate_multi_pick_multi_drop_sequence_score(plan) == Decimal("12.8")


def test_stops_over_six_add_network_complexity_points():
    plan = SequencePlan(
        pickup_count=3,
        delivery_count=4,
        direct_miles=Decimal("300"),
        planned_miles=Decimal("300"),
        stops=tuple(stop(120, 0) for _ in range(7)),
    )
    assert calculate_multi_pick_multi_drop_sequence_score(plan) == Decimal("19.0")


def test_stop_count_mismatch_is_rejected():
    plan = SequencePlan(
        pickup_count=2,
        delivery_count=1,
        direct_miles=Decimal("100"),
        planned_miles=Decimal("100"),
        stops=(stop(120, 0), stop(120, 0)),
    )
    with pytest.raises(ValueError):
        calculate_multi_pick_multi_drop_sequence_score(plan)
