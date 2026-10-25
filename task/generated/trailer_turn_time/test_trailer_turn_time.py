from datetime import datetime
from decimal import Decimal

import pytest

from trailer_turn_time import TurnMilestones, TurnRules, calculate_trailer_turn_time


def at(hour, minute=0):
    return datetime(2026, 4, 14, hour, minute)


def test_base_time_without_optional_milestones_counts_full_span():
    m = TurnMilestones(checked_in=at(8), released=at(10))
    assert calculate_trailer_turn_time(m, TurnRules(apply_grace=False)) == Decimal("2.00")


def test_pre_unload_dwell_can_be_excluded():
    m = TurnMilestones(checked_in=at(8), unload_started=at(9), released=at(11))
    rules = TurnRules(include_pre_unload_dwell=False, apply_grace=False)
    assert calculate_trailer_turn_time(m, rules) == Decimal("2.00")


def test_post_reload_dwell_can_be_excluded():
    m = TurnMilestones(checked_in=at(8), reload_completed=at(11), released=at(12))
    rules = TurnRules(include_post_reload_dwell=False, apply_grace=False)
    assert calculate_trailer_turn_time(m, rules) == Decimal("3.00")


def test_bridge_up_to_thirty_minutes_is_fully_excluded():
    m = TurnMilestones(checked_in=at(8), unload_started=at(9), reload_completed=at(9, 30), released=at(11))
    assert calculate_trailer_turn_time(m, TurnRules(apply_grace=False)) == Decimal("2.50")


def test_bridge_above_thirty_minutes_only_excludes_thirty():
    m = TurnMilestones(checked_in=at(8), unload_started=at(9), reload_completed=at(10), released=at(11))
    assert calculate_trailer_turn_time(m, TurnRules(apply_grace=False)) == Decimal("2.50")


def test_grace_applies_only_above_ninety_minutes():
    m = TurnMilestones(checked_in=at(8), released=at(9, 31))
    assert calculate_trailer_turn_time(m) == Decimal("1.25")


def test_ninety_minutes_exact_gets_no_grace():
    m = TurnMilestones(checked_in=at(8), released=at(9, 30))
    assert calculate_trailer_turn_time(m) == Decimal("1.50")


def test_rounds_half_up_to_nearest_quarter_hour():
    m = TurnMilestones(checked_in=at(8), released=at(8, 38))
    assert calculate_trailer_turn_time(m, TurnRules(apply_grace=False)) == Decimal("0.75")


def test_unload_after_reload_is_rejected():
    m = TurnMilestones(checked_in=at(8), unload_started=at(10), reload_completed=at(9), released=at(11))
    with pytest.raises(ValueError):
        calculate_trailer_turn_time(m)


def test_reload_after_release_is_rejected():
    m = TurnMilestones(checked_in=at(8), reload_completed=at(11), released=at(10))
    with pytest.raises(ValueError):
        calculate_trailer_turn_time(m)
