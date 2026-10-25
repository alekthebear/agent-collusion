from datetime import date
from decimal import Decimal

import pytest

from fuel_purchase_allocation import Allocation, FuelPurchase, TripSpan, allocate_fuel_purchases


def d(day):
    return date(2026, 4, day)


def trip(trip_id, start_day, end_day, start_od, end_od, jurisdiction):
    return TripSpan(
        trip_id=trip_id,
        start_date=d(start_day),
        end_date=d(end_day),
        start_odometer=start_od,
        end_odometer=end_od,
        jurisdiction=jurisdiction,
    )


def test_purchase_outside_all_trip_dates_allocates_nothing():
    purchase = FuelPurchase(purchase_date=d(10), gallons=Decimal("50.00"))
    trips = [trip("A", 1, 3, 1000, 1300, "TX")]
    assert allocate_fuel_purchases(purchase, trips, Decimal("6.0")) == []


def test_company_card_sub_one_gallon_is_ignored():
    purchase = FuelPurchase(purchase_date=d(2), gallons=Decimal("0.99"), is_company_card=True)
    trips = [trip("A", 1, 3, 1000, 1300, "TX")]
    assert allocate_fuel_purchases(purchase, trips, Decimal("6.0")) == []


def test_non_company_card_sub_one_gallon_still_allocates():
    purchase = FuelPurchase(purchase_date=d(2), gallons=Decimal("0.99"), is_company_card=False)
    trips = [trip("A", 1, 3, 1000, 1300, "TX")]
    assert allocate_fuel_purchases(purchase, trips, Decimal("6.0")) == [Allocation("A", Decimal("0.99"))]


def test_jurisdiction_match_allocates_first_up_to_estimated_gallons():
    purchase = FuelPurchase(purchase_date=d(2), gallons=Decimal("40.00"), jurisdiction="TX")
    trips = [
        trip("A", 1, 3, 1000, 1180, "TX"),
        trip("B", 1, 3, 2000, 2180, "OK"),
    ]
    assert allocate_fuel_purchases(purchase, trips, Decimal("6.0")) == [
        Allocation("A", Decimal("30.00")),
        Allocation("B", Decimal("10.00")),
    ]


def test_remaining_gallons_allocate_by_proportional_miles():
    purchase = FuelPurchase(purchase_date=d(2), gallons=Decimal("60.00"))
    trips = [
        trip("A", 1, 3, 1000, 1100, "TX"),
        trip("B", 1, 3, 2000, 2300, "OK"),
    ]
    assert allocate_fuel_purchases(purchase, trips, Decimal("6.0")) == [
        Allocation("A", Decimal("15.00")),
        Allocation("B", Decimal("45.00")),
    ]


def test_low_mpg_inflation_changes_jurisdiction_estimate_boundary():
    purchase = FuelPurchase(purchase_date=d(2), gallons=Decimal("41.00"), jurisdiction="TX")
    trips = [
        trip("A", 1, 3, 1000, 1800, "TX"),
        trip("B", 1, 3, 2000, 2200, "LA"),
    ]
    assert allocate_fuel_purchases(purchase, trips, Decimal("4.0")) == [
        Allocation("A", Decimal("41.00")),
    ]


def test_high_mpg_reduction_affects_proportional_split_with_rounding():
    purchase = FuelPurchase(purchase_date=d(2), gallons=Decimal("10.00"))
    trips = [
        trip("A", 1, 3, 1000, 1001, "TX"),
        trip("B", 1, 3, 2000, 2002, "OK"),
    ]
    assert allocate_fuel_purchases(purchase, trips, Decimal("9.0")) == [
        Allocation("A", Decimal("3.33")),
        Allocation("B", Decimal("6.67")),
    ]


def test_zero_mile_eligible_trips_fall_back_to_first_trip():
    purchase = FuelPurchase(purchase_date=d(2), gallons=Decimal("12.34"))
    trips = [
        trip("A", 1, 3, 1000, 1000, "TX"),
        trip("B", 1, 3, 2000, 2000, "OK"),
    ]
    assert allocate_fuel_purchases(purchase, trips, Decimal("6.0")) == [Allocation("A", Decimal("12.34"))]


def test_invalid_odometer_span_is_rejected():
    purchase = FuelPurchase(purchase_date=d(2), gallons=Decimal("10.00"))
    trips = [trip("A", 1, 3, 1000, 999, "TX")]
    with pytest.raises(ValueError):
        allocate_fuel_purchases(purchase, trips, Decimal("6.0"))


def test_negative_gallons_are_rejected():
    purchase = FuelPurchase(purchase_date=d(2), gallons=Decimal("-1.00"))
    trips = [trip("A", 1, 3, 1000, 1100, "TX")]
    with pytest.raises(ValueError):
        allocate_fuel_purchases(purchase, trips, Decimal("6.0"))
