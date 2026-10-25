from datetime import date
from decimal import Decimal

import pytest

from freeze_protection_fee import (
    FreezeProtectionRequest,
    FreezeProtectionTerms,
    calculate_freeze_protection_fee,
)


def test_no_charge_when_protection_not_requested():
    request = FreezeProtectionRequest(
        ship_date=date(2026, 1, 15),
        transit_days=2,
        lowest_forecast_f=20,
        threshold_f=34,
        region="north",
        equipment_type="dry_van",
        protection_requested=False,
    )
    assert calculate_freeze_protection_fee(request) == Decimal("0.00")


def test_reefer_never_bills_freeze_fee():
    request = FreezeProtectionRequest(
        ship_date=date(2026, 1, 15),
        transit_days=3,
        lowest_forecast_f=5,
        threshold_f=40,
        region="north",
        equipment_type="reefer",
    )
    assert calculate_freeze_protection_fee(request) == Decimal("0.00")


def test_threshold_below_34_is_not_billable():
    request = FreezeProtectionRequest(
        ship_date=date(2026, 2, 1),
        transit_days=1,
        lowest_forecast_f=20,
        threshold_f=33,
        region="north",
        equipment_type="dry_van",
    )
    assert calculate_freeze_protection_fee(request) == Decimal("0.00")


def test_north_lane_outside_season_is_free():
    request = FreezeProtectionRequest(
        ship_date=date(2026, 4, 10),
        transit_days=1,
        lowest_forecast_f=30,
        threshold_f=34,
        region="north",
        equipment_type="dry_van",
    )
    assert calculate_freeze_protection_fee(request) == Decimal("0.00")


def test_forecast_above_threshold_is_free():
    request = FreezeProtectionRequest(
        ship_date=date(2026, 12, 10),
        transit_days=2,
        lowest_forecast_f=35,
        threshold_f=34,
        region="south",
        equipment_type="dry_van",
    )
    assert calculate_freeze_protection_fee(request) == Decimal("0.00")


def test_trip_pricing_for_dry_van_at_threshold_boundary():
    request = FreezeProtectionRequest(
        ship_date=date(2026, 3, 5),
        transit_days=4,
        lowest_forecast_f=34,
        threshold_f=34,
        region="north",
        equipment_type="dry_van",
    )
    assert calculate_freeze_protection_fee(request) == Decimal("85.00")


def test_daily_pricing_bills_per_transit_day_for_heated_trailer():
    request = FreezeProtectionRequest(
        ship_date=date(2026, 1, 20),
        transit_days=3,
        lowest_forecast_f=15,
        threshold_f=36,
        region="north",
        equipment_type="heated",
    )
    terms = FreezeProtectionTerms(pricing_mode="daily")
    assert calculate_freeze_protection_fee(request, terms) == Decimal("210.00")


def test_sensitive_threshold_adds_premium():
    request = FreezeProtectionRequest(
        ship_date=date(2026, 2, 14),
        transit_days=1,
        lowest_forecast_f=25,
        threshold_f=38,
        region="north",
        equipment_type="dry_van",
    )
    assert calculate_freeze_protection_fee(request) == Decimal("105.00")


def test_extreme_cold_adds_surcharge_and_total_is_capped():
    request = FreezeProtectionRequest(
        ship_date=date(2026, 1, 8),
        transit_days=5,
        lowest_forecast_f=0,
        threshold_f=38,
        region="north",
        equipment_type="heated",
    )
    terms = FreezeProtectionTerms(pricing_mode="daily")
    assert calculate_freeze_protection_fee(request, terms) == Decimal("325.00")


def test_invalid_transit_days_is_rejected():
    request = FreezeProtectionRequest(
        ship_date=date(2026, 1, 8),
        transit_days=0,
        lowest_forecast_f=10,
        threshold_f=34,
        region="north",
        equipment_type="dry_van",
    )
    with pytest.raises(ValueError):
        calculate_freeze_protection_fee(request)
