from datetime import datetime, timedelta

import pytest

from eta_planner import DriverClocks, estimate_arrival

DEPART = datetime(2026, 10, 12, 6, 0)


def after(hours=0, minutes=0):
    return DEPART + timedelta(hours=hours, minutes=minutes)


def test_short_trip_needs_no_stops():
    plan = estimate_arrival(DEPART, 200, 50)
    assert plan.arrival == after(4)
    assert plan.stops == []


def test_break_after_eight_hours_of_driving():
    plan = estimate_arrival(DEPART, 500, 50)
    assert plan.stops == [("break", after(8))]
    assert plan.arrival == after(10, 30)


def test_eleven_hour_limit_forces_a_reset():
    plan = estimate_arrival(DEPART, 700, 50)
    assert plan.stops == [("break", after(8)), ("reset", after(11, 30))]
    assert plan.arrival == after(24, 30)


def test_partly_used_clocks_carry_into_the_plan():
    clocks = DriverClocks(drive_left=300, window_left=540, since_break=360)
    plan = estimate_arrival(DEPART, 150, 50, clocks)
    assert plan.stops == [("break", after(2))]
    assert plan.arrival == after(3, 30)
    assert clocks.since_break == 360


def test_break_due_at_the_end_of_the_window_becomes_a_reset():
    plan = estimate_arrival(DEPART, 450, 50, DriverClocks(window_left=495))
    assert plan.stops == [("reset", after(8))]
    assert plan.arrival == after(19)


def test_bad_inputs_are_rejected():
    with pytest.raises(ValueError):
        estimate_arrival(DEPART, 100, 0)
    with pytest.raises(ValueError):
        estimate_arrival(DEPART, -5, 50)


def test_break_uses_up_the_fourteen_hour_window():
    # On duty for 3h of loading before departure: 11h of window left.
    plan = estimate_arrival(DEPART, 535, 50, DriverClocks(window_left=660))
    assert plan.stops == [("break", after(8)), ("reset", after(11))]
    assert plan.arrival == after(21, 12)


def test_window_runs_out_just_after_a_break():
    plan = estimate_arrival(DEPART, 450, 50, DriverClocks(window_left=540))
    assert plan.stops == [("break", after(8)), ("reset", after(9))]
    assert plan.arrival == after(19, 30)
