from decimal import Decimal

import pytest

from mileage_payroll import DriverPayProfile, MileageTrip, calculate_mileage_payroll


def test_solo_driver_gets_all_miles_with_no_guarantee_needed():
    trip = MileageTrip(payable_miles=500)
    driver = DriverPayProfile(mileage_rate=Decimal("0.60"), guaranteed_daily_minimum=Decimal("250.00"))
    result = calculate_mileage_payroll(trip, driver)
    assert result.primary_total == Decimal("300.00")
    assert result.secondary_total == Decimal("0.00")
    assert result.primary_miles == 500
    assert result.primary_guarantee == Decimal("0.00")


def test_team_split_gives_extra_odd_mile_to_first_seat():
    trip = MileageTrip(payable_miles=101, is_team=True)
    primary = DriverPayProfile(mileage_rate=Decimal("0.50"))
    secondary = DriverPayProfile(mileage_rate=Decimal("0.50"))
    result = calculate_mileage_payroll(trip, primary, secondary)
    assert result.primary_miles == 51
    assert result.secondary_miles == 50
    assert result.primary_total == Decimal("25.50")
    assert result.secondary_total == Decimal("25.00")


def test_cross_border_premium_applies_per_driver():
    trip = MileageTrip(payable_miles=100, is_team=True, crosses_canada=True)
    primary = DriverPayProfile(mileage_rate=Decimal("0.50"))
    secondary = DriverPayProfile(mileage_rate=Decimal("0.40"))
    result = calculate_mileage_payroll(trip, primary, secondary)
    assert result.primary_total == Decimal("40.00")
    assert result.secondary_total == Decimal("35.00")


def test_guarantee_shortfall_applies_on_dispatched_days_only():
    trip = MileageTrip(payable_miles=200, dispatched_days=2)
    driver = DriverPayProfile(mileage_rate=Decimal("0.40"), guaranteed_daily_minimum=Decimal("100.00"))
    result = calculate_mileage_payroll(trip, driver)
    assert result.primary_guarantee == Decimal("120.00")
    assert result.primary_total == Decimal("200.00")


def test_short_haul_under_threshold_gets_no_guarantee():
    trip = MileageTrip(payable_miles=49)
    driver = DriverPayProfile(mileage_rate=Decimal("0.10"), guaranteed_daily_minimum=Decimal("200.00"))
    result = calculate_mileage_payroll(trip, driver)
    assert result.primary_guarantee == Decimal("0.00")
    assert result.primary_total == Decimal("4.90")


def test_exact_threshold_miles_can_still_trigger_guarantee():
    trip = MileageTrip(payable_miles=50)
    driver = DriverPayProfile(mileage_rate=Decimal("0.50"), guaranteed_daily_minimum=Decimal("60.00"))
    result = calculate_mileage_payroll(trip, driver)
    assert result.primary_guarantee == Decimal("35.00")
    assert result.primary_total == Decimal("60.00")


def test_training_pays_trainer_all_miles_and_trainee_stipend():
    trip = MileageTrip(payable_miles=300, is_training=True, trainee_stipend=Decimal("82.50"))
    trainer = DriverPayProfile(mileage_rate=Decimal("0.55"), guaranteed_daily_minimum=Decimal("100.00"))
    trainee = DriverPayProfile(mileage_rate=Decimal("0.30"), guaranteed_daily_minimum=Decimal("90.00"))
    result = calculate_mileage_payroll(trip, trainer, trainee)
    assert result.primary_miles == 300
    assert result.secondary_miles == 0
    assert result.primary_total == Decimal("165.00")
    assert result.secondary_total == Decimal("172.50")
    assert result.secondary_guarantee == Decimal("90.00")


def test_half_up_rounding_applies_to_fractional_cent_mileage():
    trip = MileageTrip(payable_miles=3)
    driver = DriverPayProfile(mileage_rate=Decimal("0.335"))
    result = calculate_mileage_payroll(trip, driver)
    assert result.primary_total == Decimal("1.01")


def test_team_trip_requires_secondary_driver():
    trip = MileageTrip(payable_miles=100, is_team=True)
    driver = DriverPayProfile(mileage_rate=Decimal("0.50"))
    with pytest.raises(ValueError):
        calculate_mileage_payroll(trip, driver)
