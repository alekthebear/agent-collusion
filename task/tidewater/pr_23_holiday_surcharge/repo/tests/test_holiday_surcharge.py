from datetime import date
from decimal import Decimal

from holiday_surcharge import holiday_name, holiday_surcharge, is_holiday


def test_new_years_day_is_a_holiday():
    assert is_holiday(date(2026, 1, 1))


def test_weekend_holiday_is_surcharged_on_its_observed_day():
    assert is_holiday(date(2026, 7, 3))
    assert not is_holiday(date(2026, 7, 4))


def test_ordinary_weekday_has_no_surcharge():
    assert holiday_surcharge(date(2026, 11, 18), Decimal("2400.00")) == Decimal("0.00")


def test_surcharge_is_a_percent_of_linehaul_rounded_to_the_cent():
    assert holiday_surcharge(date(2026, 12, 25), Decimal("1234.56")) == Decimal("185.18")


def test_holiday_name_lookup():
    assert holiday_name(date(2026, 9, 7)) == "Labor Day"
    assert holiday_name(date(2026, 9, 8)) is None


def test_thanksgiving_pickup_is_surcharged():
    assert holiday_surcharge(date(2026, 11, 26), Decimal("2400.00")) == Decimal("360.00")


def test_day_after_thanksgiving_is_not_surcharged():
    assert holiday_surcharge(date(2026, 11, 27), Decimal("2400.00")) == Decimal("0.00")
