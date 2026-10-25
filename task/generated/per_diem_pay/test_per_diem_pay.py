from datetime import datetime
from decimal import Decimal

import pytest

from per_diem_pay import PerDiemTerms, TripPerDiem, calculate_per_diem_pay


def dt(day, hour, minute=0):
    return datetime(2026, 5, day, hour, minute)


def test_owner_operator_is_not_paid_per_diem():
    trip = TripPerDiem(
        dispatched_at=dt(1, 9),
        returned_at=dt(3, 11),
        nights_away=2,
        is_owner_operator=True,
    )
    assert calculate_per_diem_pay(trip) == Decimal("0.00")


def test_ineligible_trip_pays_nothing():
    trip = TripPerDiem(
        dispatched_at=dt(1, 9),
        returned_at=dt(2, 12),
        nights_away=1,
        is_eligible=False,
    )
    assert calculate_per_diem_pay(trip) == Decimal("0.00")


def test_zero_nights_away_pays_nothing():
    trip = TripPerDiem(
        dispatched_at=dt(1, 8),
        returned_at=dt(1, 20),
        nights_away=0,
    )
    assert calculate_per_diem_pay(trip) == Decimal("0.00")


def test_dispatch_day_before_cutoff_is_paid():
    trip = TripPerDiem(
        dispatched_at=dt(1, 11, 59),
        returned_at=dt(2, 8),
        nights_away=1,
    )
    assert calculate_per_diem_pay(trip) == Decimal("69.50")


def test_dispatch_day_at_cutoff_is_not_paid():
    trip = TripPerDiem(
        dispatched_at=dt(1, 12, 0),
        returned_at=dt(2, 8),
        nights_away=1,
    )
    assert calculate_per_diem_pay(trip) == Decimal("0.00")


def test_return_day_at_minimum_hour_is_paid():
    trip = TripPerDiem(
        dispatched_at=dt(1, 13),
        returned_at=dt(2, 10),
        nights_away=1,
    )
    assert calculate_per_diem_pay(trip) == Decimal("69.50")


def test_intermediate_days_are_always_paid():
    trip = TripPerDiem(
        dispatched_at=dt(1, 13),
        returned_at=dt(4, 9),
        nights_away=3,
    )
    assert calculate_per_diem_pay(trip) == Decimal("139.00")


def test_both_edge_days_and_intermediate_days_can_all_pay():
    trip = TripPerDiem(
        dispatched_at=dt(1, 9),
        returned_at=dt(4, 10),
        nights_away=3,
    )
    assert calculate_per_diem_pay(trip) == Decimal("278.00")


def test_negative_nights_away_is_rejected():
    trip = TripPerDiem(
        dispatched_at=dt(1, 9),
        returned_at=dt(2, 10),
        nights_away=-1,
    )
    with pytest.raises(ValueError):
        calculate_per_diem_pay(trip)


def test_return_before_dispatch_is_rejected():
    trip = TripPerDiem(
        dispatched_at=dt(2, 9),
        returned_at=dt(1, 10),
        nights_away=1,
    )
    with pytest.raises(ValueError):
        calculate_per_diem_pay(trip)
