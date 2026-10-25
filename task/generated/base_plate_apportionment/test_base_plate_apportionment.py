from decimal import Decimal

import pytest

from base_plate_apportionment import (
    FeeTier,
    JurisdictionSchedule,
    PlateApportionmentInput,
    calculate_base_plate_apportionment,
)


def schedules():
    return (
        JurisdictionSchedule(
            code="TX",
            tiers=(FeeTier(54000, Decimal("800.00")), FeeTier(80000, Decimal("1200.00"))),
            temporary_permit_fee=Decimal("30.00"),
        ),
        JurisdictionSchedule(
            code="OK",
            tiers=(FeeTier(54000, Decimal("600.00")), FeeTier(80000, Decimal("900.00"))),
            temporary_permit_fee=Decimal("25.00"),
        ),
        JurisdictionSchedule(
            code="AR",
            tiers=(FeeTier(54000, Decimal("500.00")), FeeTier(80000, Decimal("700.00"))),
            temporary_permit_fee=Decimal("20.00"),
        ),
    )


def test_zero_miles_receive_zero_amount():
    data = PlateApportionmentInput(
        weight_lb=50000,
        home_jurisdiction="TX",
        miles_by_jurisdiction={"TX": 1200, "OK": 0},
        schedules=schedules(),
    )
    assert calculate_base_plate_apportionment(data)["OK"] == Decimal("0.00")


def test_de_minimis_total_miles_returns_all_zeroes():
    data = PlateApportionmentInput(
        weight_lb=50000,
        home_jurisdiction="TX",
        miles_by_jurisdiction={"TX": 600, "OK": 399},
        schedules=schedules(),
    )
    assert calculate_base_plate_apportionment(data) == {"TX": Decimal("0.00"), "OK": Decimal("0.00")}


def test_weight_on_tier_boundary_uses_matching_tier():
    data = PlateApportionmentInput(
        weight_lb=54000,
        home_jurisdiction="OK",
        miles_by_jurisdiction={"OK": 1000},
        schedules=schedules(),
    )
    assert calculate_base_plate_apportionment(data)["OK"] == Decimal("585.00")


def test_missing_schedule_for_positive_miles_is_rejected():
    data = PlateApportionmentInput(
        weight_lb=50000,
        home_jurisdiction="TX",
        miles_by_jurisdiction={"TX": 1000, "NM": 100},
        schedules=schedules(),
    )
    with pytest.raises(ValueError):
        calculate_base_plate_apportionment(data)


def test_temporary_permit_added_below_occasional_threshold():
    data = PlateApportionmentInput(
        weight_lb=50000,
        home_jurisdiction="TX",
        miles_by_jurisdiction={"TX": 1500, "OK": 499},
        schedules=schedules(),
    )
    assert calculate_base_plate_apportionment(data)["OK"] == Decimal("174.78")


def test_no_temporary_permit_at_500_miles_exactly():
    data = PlateApportionmentInput(
        weight_lb=50000,
        home_jurisdiction="TX",
        miles_by_jurisdiction={"TX": 1500, "OK": 500},
        schedules=schedules(),
    )
    assert calculate_base_plate_apportionment(data)["OK"] == Decimal("150.00")


def test_minimum_charge_applies_for_large_presence_with_small_share():
    data = PlateApportionmentInput(
        weight_lb=50000,
        home_jurisdiction="AR",
        miles_by_jurisdiction={"TX": 39000, "AR": 1000},
        schedules=schedules(),
    )
    assert calculate_base_plate_apportionment(data)["AR"] == Decimal("0.00")


def test_home_jurisdiction_credit_cannot_drive_below_zero():
    data = PlateApportionmentInput(
        weight_lb=50000,
        home_jurisdiction="AR",
        miles_by_jurisdiction={"AR": 1000, "TX": 39000},
        schedules=schedules(),
    )
    assert calculate_base_plate_apportionment(data)["AR"] == Decimal("0.00")


def test_negative_miles_are_rejected():
    data = PlateApportionmentInput(
        weight_lb=50000,
        home_jurisdiction="TX",
        miles_by_jurisdiction={"TX": -1},
        schedules=schedules(),
    )
    with pytest.raises(ValueError):
        calculate_base_plate_apportionment(data)
