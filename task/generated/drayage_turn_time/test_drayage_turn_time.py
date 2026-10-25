from datetime import datetime
from decimal import Decimal

import pytest

from drayage_turn_time import TerminalVisit, TurnTimeRules, calculate_drayage_turn_time


def at(hour, minute=0):
    return datetime(2026, 4, 14, hour, minute)


def test_basic_gate_to_gate_turn_time_rounds_to_tenth():
    visit = TerminalVisit(in_gate=at(8), out_gate=at(9, 7))
    assert calculate_drayage_turn_time(visit) == Decimal("1.1")


def test_early_arrival_starts_clock_at_appointment():
    visit = TerminalVisit(in_gate=at(7, 30), out_gate=at(9, 0), appointment=at(8, 0))
    assert calculate_drayage_turn_time(visit) == Decimal("1.0")


def test_late_arrival_starts_clock_at_in_gate():
    visit = TerminalVisit(in_gate=at(8, 20), out_gate=at(9, 20), appointment=at(8, 0))
    assert calculate_drayage_turn_time(visit) == Decimal("1.0")


def test_short_visit_gets_yard_flip_minimum():
    visit = TerminalVisit(in_gate=at(10, 0), out_gate=at(10, 12))
    assert calculate_drayage_turn_time(visit) == Decimal("0.3")


def test_exact_yard_flip_threshold_is_not_forced_to_minimum():
    visit = TerminalVisit(in_gate=at(10, 0), out_gate=at(10, 18))
    assert calculate_drayage_turn_time(visit) == Decimal("0.3")


def test_split_move_subtracts_pause_when_it_meets_minimum():
    visit = TerminalVisit(
        in_gate=at(8, 0),
        out_gate=at(10, 0),
        split_move=True,
        first_leg_complete=at(8, 40),
        second_leg_start=at(9, 5),
    )
    assert calculate_drayage_turn_time(visit) == Decimal("1.6")


def test_split_move_pause_under_minimum_gets_no_credit():
    visit = TerminalVisit(
        in_gate=at(8, 0),
        out_gate=at(10, 0),
        split_move=True,
        first_leg_complete=at(8, 40),
        second_leg_start=at(8, 59),
    )
    assert calculate_drayage_turn_time(visit) == Decimal("2.0")


def test_split_move_credit_is_capped_at_forty_five_minutes():
    visit = TerminalVisit(
        in_gate=at(8, 0),
        out_gate=at(11, 0),
        split_move=True,
        first_leg_complete=at(8, 30),
        second_leg_start=at(9, 45),
    )
    assert calculate_drayage_turn_time(visit) == Decimal("2.3")


def test_trouble_window_adds_time_only_for_long_visits():
    visit = TerminalVisit(in_gate=at(8, 0), out_gate=at(11, 30), trouble_window=True)
    assert calculate_drayage_turn_time(visit) == Decimal("3.7")


def test_incomplete_split_milestones_are_rejected():
    with pytest.raises(ValueError):
        calculate_drayage_turn_time(
            TerminalVisit(
                in_gate=at(8, 0),
                out_gate=at(9, 0),
                split_move=True,
                first_leg_complete=at(8, 20),
            )
        )
