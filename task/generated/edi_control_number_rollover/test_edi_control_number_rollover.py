from edi_control_number_rollover import (
    ControlNumberRange,
    ControlNumberState,
    RolloverPolicy,
    calculate_edi_control_number_rollover,
)

import pytest


def test_simple_increment_inside_range():
    state = ControlNumberState(current_value=104)
    assert calculate_edi_control_number_rollover(state) == 105


def test_custom_step_advances_exactly():
    state = ControlNumberState(
        current_value=120,
        policy=RolloverPolicy(step=5),
    )
    assert calculate_edi_control_number_rollover(state) == 125


def test_hitting_maximum_exactly_is_allowed_without_rollover():
    state = ControlNumberState(
        current_value=999998,
        policy=RolloverPolicy(allow_rollover=False, step=1),
    )
    assert calculate_edi_control_number_rollover(state) == 999999


def test_rollover_returns_minimum_when_no_holdback():
    state = ControlNumberState(
        current_value=999999,
        policy=RolloverPolicy(allow_rollover=True, step=1, hold_low_values=0),
    )
    assert calculate_edi_control_number_rollover(state) == 1


def test_rollover_skips_reserved_low_values():
    state = ControlNumberState(
        current_value=500,
        number_range=ControlNumberRange(minimum=100, maximum=500, strict_six_digit=True),
        policy=RolloverPolicy(allow_rollover=True, step=10, hold_low_values=7),
    )
    assert calculate_edi_control_number_rollover(state) == 107


def test_rollover_disabled_raises_when_step_passes_maximum():
    state = ControlNumberState(
        current_value=999999,
        policy=RolloverPolicy(allow_rollover=False, step=1),
    )
    with pytest.raises(ValueError):
        calculate_edi_control_number_rollover(state)


def test_current_value_outside_bounds_is_rejected():
    state = ControlNumberState(
        current_value=99,
        number_range=ControlNumberRange(minimum=100, maximum=999, strict_six_digit=True),
    )
    with pytest.raises(ValueError):
        calculate_edi_control_number_rollover(state)


def test_holdback_consuming_entire_window_is_rejected():
    state = ControlNumberState(
        current_value=5,
        number_range=ControlNumberRange(minimum=1, maximum=5, strict_six_digit=True),
        policy=RolloverPolicy(allow_rollover=True, step=1, hold_low_values=5),
    )
    with pytest.raises(ValueError):
        calculate_edi_control_number_rollover(state)


def test_non_strict_mode_allows_zero_based_range_and_rollover():
    state = ControlNumberState(
        current_value=12,
        number_range=ControlNumberRange(minimum=0, maximum=12, strict_six_digit=False),
        policy=RolloverPolicy(allow_rollover=True, step=1, hold_low_values=0),
    )
    assert calculate_edi_control_number_rollover(state) == 0
