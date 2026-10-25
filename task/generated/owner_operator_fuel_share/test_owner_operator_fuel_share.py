from decimal import Decimal

import pytest

from owner_operator_fuel_share import (
    FuelShareInputs,
    FuelShareTerms,
    calculate_owner_operator_fuel_share,
)


def test_including_empty_miles_uses_full_billed_fsc():
    inputs = FuelShareInputs(billed_fsc=Decimal("100.00"), loaded_miles=200, empty_miles=50)
    terms = FuelShareTerms(share_percent=Decimal("70"))
    assert calculate_owner_operator_fuel_share(inputs, terms) == Decimal("70.00")


def test_excluding_empty_miles_prorates_to_loaded_portion():
    inputs = FuelShareInputs(
        billed_fsc=Decimal("100.00"),
        loaded_miles=200,
        empty_miles=50,
        include_empty_miles=False,
    )
    terms = FuelShareTerms(share_percent=Decimal("70"))
    assert calculate_owner_operator_fuel_share(inputs, terms) == Decimal("56.00")


def test_local_move_retains_first_five_dollars_before_split():
    inputs = FuelShareInputs(billed_fsc=Decimal("20.00"), loaded_miles=49, empty_miles=0)
    terms = FuelShareTerms(share_percent=Decimal("80"))
    assert calculate_owner_operator_fuel_share(inputs, terms) == Decimal("12.00")


def test_short_move_boundary_at_fifty_miles_uses_two_fifty_retention():
    inputs = FuelShareInputs(billed_fsc=Decimal("20.00"), loaded_miles=50, empty_miles=0)
    terms = FuelShareTerms(share_percent=Decimal("80"))
    assert calculate_owner_operator_fuel_share(inputs, terms) == Decimal("14.00")


def test_no_retention_starts_at_one_hundred_fifty_loaded_miles():
    inputs = FuelShareInputs(billed_fsc=Decimal("20.00"), loaded_miles=150, empty_miles=0)
    terms = FuelShareTerms(share_percent=Decimal("80"))
    assert calculate_owner_operator_fuel_share(inputs, terms) == Decimal("16.00")


def test_de_minimis_payout_under_one_dollar_is_zero():
    inputs = FuelShareInputs(billed_fsc=Decimal("1.50"), loaded_miles=200, empty_miles=0)
    terms = FuelShareTerms(share_percent=Decimal("65"))
    assert calculate_owner_operator_fuel_share(inputs, terms) == Decimal("0.00")


def test_half_up_rounding_applies_to_fractional_cents():
    inputs = FuelShareInputs(billed_fsc=Decimal("10.01"), loaded_miles=200, empty_miles=0)
    terms = FuelShareTerms(share_percent=Decimal("33.333"))
    assert calculate_owner_operator_fuel_share(inputs, terms) == Decimal("3.34")


def test_zero_total_miles_returns_zero_even_with_billed_fsc():
    inputs = FuelShareInputs(billed_fsc=Decimal("25.00"), loaded_miles=0, empty_miles=0)
    assert calculate_owner_operator_fuel_share(inputs) == Decimal("0.00")


def test_loaded_zero_and_empty_excluded_returns_zero():
    inputs = FuelShareInputs(
        billed_fsc=Decimal("25.00"),
        loaded_miles=0,
        empty_miles=100,
        include_empty_miles=False,
    )
    assert calculate_owner_operator_fuel_share(inputs) == Decimal("0.00")


def test_invalid_share_percent_is_rejected():
    with pytest.raises(ValueError):
        calculate_owner_operator_fuel_share(
            FuelShareInputs(billed_fsc=Decimal("10.00"), loaded_miles=100),
            FuelShareTerms(share_percent=Decimal("100.01")),
        )
