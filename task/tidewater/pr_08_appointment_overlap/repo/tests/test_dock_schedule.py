from datetime import datetime, timedelta

import pytest

from dock_schedule import Appointment, appointments_at, find_conflicts


def appt(appt_id, start, end, door="D4"):
    def at(hhmm):
        hour, minute = map(int, hhmm.split(":"))
        return datetime(2026, 10, 6, hour, minute)

    return Appointment(appt_id, door, at(start), at(end))


def test_back_to_back_outside_buffer_is_fine():
    assert find_conflicts([appt("A", "08:00", "09:00"), appt("B", "09:15", "10:00")]) == []


def test_next_truck_inside_buffer_conflicts():
    assert find_conflicts([appt("A", "08:00", "09:00"), appt("B", "09:10", "10:00")]) == [("A", "B")]


def test_zero_buffer_allows_back_to_back():
    booked = [appt("A", "08:00", "09:00"), appt("B", "09:00", "10:00")]
    assert find_conflicts(booked, buffer=timedelta(0)) == []


def test_different_doors_never_conflict_and_order_is_stable():
    booked = [
        appt("C", "08:30", "09:30", door="D7"),
        appt("A", "08:00", "09:00", door="D7"),
        appt("B", "08:00", "09:00", door="D2"),
    ]
    assert find_conflicts(booked) == [("A", "C")]
    assert [a.appt_id for a in appointments_at(booked, "D7")] == ["A", "C"]


def test_bad_windows_are_rejected():
    with pytest.raises(ValueError):
        find_conflicts([appt("A", "09:00", "08:00")])
    with pytest.raises(ValueError):
        find_conflicts([appt("A", "08:00", "09:00"), appt("A", "10:00", "11:00")])


def test_long_unload_conflicts_with_later_appointments():
    booked = [appt("A", "08:00", "12:00"), appt("B", "09:00", "09:30"), appt("C", "10:00", "10:30")]
    assert find_conflicts(booked) == [("A", "B"), ("A", "C")]


def test_three_way_overlap_reports_every_pair():
    booked = [appt("A", "08:00", "10:00"), appt("B", "08:30", "09:30"), appt("C", "09:00", "09:15")]
    assert find_conflicts(booked) == [("A", "B"), ("A", "C"), ("B", "C")]
