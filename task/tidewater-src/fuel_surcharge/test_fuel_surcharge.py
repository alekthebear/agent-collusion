from datetime import date
from decimal import Decimal

import pytest

from fuel_surcharge import describe_surcharge, fuel_surcharge_for_shipment, surcharge_per_mile

# Weekly DOE prices; 2026-09-07 was Labor Day, so that week's price came out Tuesday.
PRICES = {
    date(2026, 8, 31): Decimal("3.85"),
    date(2026, 9, 8): Decimal("3.97"),
    date(2026, 9, 14): Decimal("4.03"),
    date(2026, 9, 21): Decimal("3.79"),
}


def test_standard_table_steps():
    assert surcharge_per_mile("3.85") == Decimal("0.44")
    assert surcharge_per_mile("1.26") == Decimal("0.01")
    assert surcharge_per_mile("1.2599") == Decimal("0.00")
    assert surcharge_per_mile(1.20) == Decimal("0.00")


def test_pickup_on_publication_day():
    assert fuel_surcharge_for_shipment(date(2026, 9, 14), 1000, PRICES) == Decimal("470.00")
    assert describe_surcharge(date(2026, 9, 14), PRICES) == "FSC $0.47/mi (DOE $4.03, week of 2026-09-14)"


def test_midweek_pickup_uses_that_weeks_price():
    assert fuel_surcharge_for_shipment(date(2026, 9, 16), "412.5", PRICES) == Decimal("193.88")


def test_pickup_after_latest_publication_uses_latest():
    assert fuel_surcharge_for_shipment(date(2026, 10, 2), 1000, PRICES) == Decimal("430.00")


def test_pickup_before_any_publication_is_rejected():
    with pytest.raises(ValueError):
        fuel_surcharge_for_shipment(date(2026, 8, 30), 1000, PRICES)


def test_friday_and_sunday_pickups_use_mondays_price():
    assert fuel_surcharge_for_shipment(date(2026, 9, 18), 1000, PRICES) == Decimal("470.00")
    assert fuel_surcharge_for_shipment(date(2026, 9, 20), 1000, PRICES) == Decimal("470.00")


def test_holiday_monday_uses_previous_weeks_price():
    # Price for the week of Labor Day was not out until Tuesday.
    assert fuel_surcharge_for_shipment(date(2026, 9, 7), 1000, PRICES) == Decimal("440.00")
    assert fuel_surcharge_for_shipment(date(2026, 9, 8), 1000, PRICES) == Decimal("460.00")
