from datetime import datetime
from decimal import Decimal

import pytest

from trailer_rental_deduction import (
    RentalPeriod,
    RentalTerms,
    Utilization,
    calculate_trailer_rental_deduction,
)


def at(day, hour=0, minute=0):
    return datetime(2026, 4, day, hour, minute)


def test_yard_turn_of_six_hours_or_less_is_free():
    period = RentalPeriod(picked_up=at(1, 8), returned=at(1, 14))
    assert calculate_trailer_rental_deduction(period) == Decimal("0.00")


def test_started_day_after_free_hours_bills_one_day():
    period = RentalPeriod(picked_up=at(1, 8), returned=at(1, 14, 1))
    assert calculate_trailer_rental_deduction(period) == Decimal("28.00")


def test_six_billable_days_use_daily_rate():
    period = RentalPeriod(picked_up=at(1, 8), returned=at(7, 8, 1))
    assert calculate_trailer_rental_deduction(period) == Decimal("168.00")


def test_seven_billable_days_convert_to_weekly_rate():
    period = RentalPeriod(picked_up=at(1, 8), returned=at(8, 8, 1))
    assert calculate_trailer_rental_deduction(period) == Decimal("175.00")


def test_weekly_proration_rounds_half_up_for_partial_week():
    period = RentalPeriod(picked_up=at(1, 8), returned=at(10, 8, 1))
    assert calculate_trailer_rental_deduction(period) == Decimal("225.00")


def test_moderate_utilization_waives_one_billable_day():
    period = RentalPeriod(picked_up=at(1, 8), returned=at(3, 8, 1))
    utilization = Utilization(loaded_moves=1, loaded_miles=500)
    assert calculate_trailer_rental_deduction(period, utilization) == Decimal("28.00")


def test_high_utilization_waives_rental_and_reefer_but_not_damage_hold():
    period = RentalPeriod(picked_up=at(1, 8), returned=at(4, 9), trailer_type="reefer")
    utilization = Utilization(loaded_moves=2, loaded_miles=1000)
    terms = RentalTerms(damage_hold=Decimal("35.25"))
    assert calculate_trailer_rental_deduction(period, utilization, terms) == Decimal("35.25")


def test_reefer_adds_daily_surcharge_per_charged_day():
    period = RentalPeriod(picked_up=at(1, 8), returned=at(3, 8, 1), trailer_type="reefer")
    assert calculate_trailer_rental_deduction(period) == Decimal("75.00")


def test_damage_hold_is_added_after_other_charges():
    period = RentalPeriod(picked_up=at(1, 8), returned=at(1, 14, 1))
    terms = RentalTerms(damage_hold=Decimal("12.34"))
    assert calculate_trailer_rental_deduction(period, terms=terms) == Decimal("40.34")


def test_return_before_pickup_is_rejected():
    period = RentalPeriod(picked_up=at(2, 10), returned=at(2, 9))
    with pytest.raises(ValueError):
        calculate_trailer_rental_deduction(period)
