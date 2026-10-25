from datetime import date

import pytest

from trailer_inspection_due import (
    InspectionDueStatus,
    TrailerInspectionRecord,
    calculate_trailer_inspection_due,
)


def day(n):
    return date(2026, 1, 1) + __import__("datetime").timedelta(days=n)


def test_standard_trailer_not_yet_due_returns_remaining_time_and_miles():
    record = TrailerInspectionRecord(
        last_inspection_date=day(0),
        last_inspection_odometer=100000,
        current_date=day(30),
        current_odometer=104000,
    )
    status = calculate_trailer_inspection_due(record)
    assert status == InspectionDueStatus(
        due_date=day(90),
        due_odometer=112000,
        overdue=False,
        overdue_by_days=0,
        overdue_by_miles=0,
        remaining_days=60,
        remaining_miles=8000,
        reason="standard",
    )


def test_exact_due_date_counts_as_due():
    record = TrailerInspectionRecord(
        last_inspection_date=day(0),
        last_inspection_odometer=5000,
        current_date=day(90),
        current_odometer=16000,
    )
    status = calculate_trailer_inspection_due(record)
    assert status.overdue is True
    assert status.overdue_by_days == 0
    assert status.overdue_by_miles == 0


def test_exact_due_odometer_counts_as_due():
    record = TrailerInspectionRecord(
        last_inspection_date=day(0),
        last_inspection_odometer=5000,
        current_date=day(20),
        current_odometer=17000,
    )
    status = calculate_trailer_inspection_due(record)
    assert status.due_odometer == 17000
    assert status.overdue is True
    assert status.remaining_miles == 0


def test_reefer_uses_shorter_base_intervals():
    record = TrailerInspectionRecord(
        last_inspection_date=day(0),
        last_inspection_odometer=20000,
        current_date=day(59),
        current_odometer=29999,
        equipment_type="reefer",
    )
    status = calculate_trailer_inspection_due(record)
    assert status.due_date == day(60)
    assert status.due_odometer == 30000
    assert status.overdue is False
    assert status.reason == "reefer"


def test_california_tightens_standard_calendar_limit_only():
    record = TrailerInspectionRecord(
        last_inspection_date=day(0),
        last_inspection_odometer=90000,
        current_date=day(74),
        current_odometer=95000,
        jurisdiction="ca",
    )
    status = calculate_trailer_inspection_due(record)
    assert status.due_date == day(75)
    assert status.due_odometer == 102000
    assert status.remaining_days == 1
    assert status.reason == "standard+ca"


def test_california_does_not_extend_hazmat_shorter_cycle():
    record = TrailerInspectionRecord(
        last_inspection_date=day(0),
        last_inspection_odometer=40000,
        current_date=day(44),
        current_odometer=47000,
        equipment_type="hazmat",
        jurisdiction="ca",
    )
    status = calculate_trailer_inspection_due(record)
    assert status.due_date == day(45)
    assert status.reason == "hazmat"


def test_failed_inspection_tightens_to_reinspection_limits():
    record = TrailerInspectionRecord(
        last_inspection_date=day(0),
        last_inspection_odometer=70000,
        current_date=day(6),
        current_odometer=70499,
        last_result="fail",
    )
    status = calculate_trailer_inspection_due(record)
    assert status.due_date == day(7)
    assert status.due_odometer == 70500
    assert status.overdue is False
    assert status.reason == "standard+reinspect"


def test_roadside_hold_is_immediately_overdue_even_before_thresholds():
    record = TrailerInspectionRecord(
        last_inspection_date=day(0),
        last_inspection_odometer=1000,
        current_date=day(1),
        current_odometer=1001,
        roadside_defect_hold=True,
    )
    status = calculate_trailer_inspection_due(record)
    assert status.overdue is True
    assert status.reason == "standard+hold"
    assert status.overdue_by_days == 0
    assert status.overdue_by_miles == 0


def test_past_both_thresholds_reports_overages():
    record = TrailerInspectionRecord(
        last_inspection_date=day(0),
        last_inspection_odometer=100000,
        current_date=day(95),
        current_odometer=112123,
    )
    status = calculate_trailer_inspection_due(record)
    assert status.overdue is True
    assert status.overdue_by_days == 5
    assert status.overdue_by_miles == 123


def test_odometer_cannot_go_backwards():
    record = TrailerInspectionRecord(
        last_inspection_date=day(0),
        last_inspection_odometer=5000,
        current_date=day(1),
        current_odometer=4999,
    )
    with pytest.raises(ValueError):
        calculate_trailer_inspection_due(record)
