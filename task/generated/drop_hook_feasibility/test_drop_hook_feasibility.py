from decimal import Decimal

import pytest

from drop_hook_feasibility import (
    EquipmentRules,
    YardInventory,
    evaluate_drop_hook_feasibility,
)


def yard(**overrides):
    base = dict(on_hand=3, expected_returns_today=0, reserved=0, capacity=20)
    base.update(overrides)
    return YardInventory(**base)


def rules(**overrides):
    base = dict(shipper_allows_drop=True, receiver_allows_hook=True)
    base.update(overrides)
    return EquipmentRules(**base)


def test_basic_dry_load_with_exact_minimum_pool_is_feasible():
    decision = evaluate_drop_hook_feasibility(yard(on_hand=2), yard(on_hand=2), rules())
    assert decision.feasible is True
    assert decision.reason == "feasible"
    assert decision.shipper_usable == 2
    assert decision.receiver_usable == 2


def test_shipper_must_allow_drop():
    decision = evaluate_drop_hook_feasibility(yard(on_hand=5), yard(on_hand=5), rules(shipper_allows_drop=False))
    assert decision.feasible is False
    assert decision.reason == "shipper_no_drop"
    assert decision.shipper_usable == 0
    assert decision.receiver_usable == 0


def test_returns_minus_reserved_count_toward_usable_pool():
    decision = evaluate_drop_hook_feasibility(
        yard(on_hand=1, expected_returns_today=2, reserved=1),
        yard(on_hand=2),
        rules(),
    )
    assert decision.feasible is True
    assert decision.shipper_usable == 2
    assert decision.receiver_usable == 2


def test_reefer_requires_ready_yards_and_deeper_pool():
    decision = evaluate_drop_hook_feasibility(
        yard(on_hand=3, reefer_ready=True),
        yard(on_hand=2, reefer_ready=True),
        rules(refrigerated=True),
    )
    assert decision.feasible is False
    assert decision.reason == "receiver_pool_short"


def test_hazmat_requires_approval_at_both_yards():
    decision = evaluate_drop_hook_feasibility(
        yard(on_hand=4, hazmat_approved=True),
        yard(on_hand=4, hazmat_approved=False),
        rules(hazmat=True),
    )
    assert decision.feasible is False
    assert decision.reason == "hazmat_not_supported"


def test_weight_boundary_allows_exact_dry_limit():
    decision = evaluate_drop_hook_feasibility(
        yard(on_hand=3),
        yard(on_hand=3),
        rules(estimated_weight_lb=44000),
    )
    assert decision.feasible is True
    assert decision.reason == "feasible"


def test_reefer_weight_above_lower_limit_is_rejected():
    decision = evaluate_drop_hook_feasibility(
        yard(on_hand=4, reefer_ready=True),
        yard(on_hand=4, reefer_ready=True),
        rules(refrigerated=True, estimated_weight_lb=42501),
    )
    assert decision.feasible is False
    assert decision.reason == "weight_exceeds_pool_limit"


def test_tight_pickup_adds_one_required_trailer():
    decision = evaluate_drop_hook_feasibility(
        yard(on_hand=2),
        yard(on_hand=2),
        rules(pickup_lead_hours=Decimal("3.99")),
    )
    assert decision.feasible is False
    assert decision.reason == "shipper_pool_short"


def test_high_utilization_over_limit_blocks_even_with_inventory():
    decision = evaluate_drop_hook_feasibility(
        yard(on_hand=10, capacity=10),
        yard(on_hand=10, capacity=10),
        rules(),
    )
    assert decision.feasible is False
    assert decision.reason == "shipper_yard_full"


def test_utilization_band_from_85_to_92_needs_one_extra_trailer():
    decision = evaluate_drop_hook_feasibility(
        yard(on_hand=17, capacity=20),
        yard(on_hand=2),
        rules(),
    )
    assert decision.feasible is True
    assert decision.reason == "feasible"
    edge_fail = evaluate_drop_hook_feasibility(
        yard(on_hand=2, capacity=20, utilization_override=Decimal("0.85")),
        yard(on_hand=2),
        rules(),
    )
    assert edge_fail.feasible is False
    assert edge_fail.reason == "shipper_pool_short"
