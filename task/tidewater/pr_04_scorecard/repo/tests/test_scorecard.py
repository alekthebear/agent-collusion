from datetime import datetime, timedelta

from scorecard import Delivery, on_time_percentage, scorecard_counts

WINDOW_END = datetime(2026, 9, 14, 12, 0)


def delivered(load_id, minutes_after_window, code=None):
    return Delivery(
        load_id=load_id,
        window_end=WINDOW_END,
        delivered_at=WINDOW_END + timedelta(minutes=minutes_after_window),
        delay_code=code,
    )


def test_all_on_time_is_100():
    loads = [delivered("A", -90), delivered("B", 0), delivered("C", 10)]
    assert on_time_percentage(loads) == 100.0


def test_grace_period_boundary():
    assert on_time_percentage([delivered("A", 15)]) == 100.0
    assert on_time_percentage([delivered("A", 16)]) == 0.0


def test_cancelled_and_in_transit_loads_are_not_measured():
    loads = [
        delivered("A", 0),
        delivered("B", 120),
        Delivery("C", WINDOW_END, status="cancelled"),
        Delivery("D", WINDOW_END, status="in_transit"),
    ]
    assert on_time_percentage(loads) == 50.0


def test_on_time_load_with_a_delay_code_still_counts():
    loads = [delivered("A", 5, code="CUST"), delivered("B", 90)]
    assert on_time_percentage(loads) == 50.0


def test_counts_breakdown():
    loads = [
        delivered("A", 0),
        delivered("B", 45, code="WX"),
        delivered("C", 45, code="CARR"),
        Delivery("D", WINDOW_END, status="cancelled"),
    ]
    assert scorecard_counts(loads) == {"on_time": 1, "late": 1, "excused": 1, "skipped": 1}


def test_empty_period_is_none():
    assert on_time_percentage([]) is None


def test_excused_late_deliveries_are_left_out():
    loads = [delivered(f"OT{i}", 0) for i in range(7)]
    loads += [delivered("L1", 60, code="CUST"), delivered("L2", 75, code="CONS")]
    loads += [delivered("L3", 30, code="CARR")]
    assert on_time_percentage(loads) == 87.5


def test_period_with_only_excused_lates_is_none():
    loads = [delivered("A", 200, code="WX"), Delivery("B", WINDOW_END, status="cancelled")]
    assert on_time_percentage(loads) is None
