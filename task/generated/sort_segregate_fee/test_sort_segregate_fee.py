from decimal import Decimal

import pytest

from sort_segregate_fee import (
    SortSegregateStop,
    SortSegregateTerms,
    calculate_sort_segregate_fee,
)


def test_small_simple_load_is_not_billable():
    stop = SortSegregateStop(sku_count=7, pallet_count=2, total_lines=7)
    assert calculate_sort_segregate_fee(stop) == Decimal("0.00")


def test_sku_threshold_of_eight_triggers_minimum_fee():
    stop = SortSegregateStop(sku_count=8, pallet_count=2, total_lines=8)
    assert calculate_sort_segregate_fee(stop) == Decimal("65.00")


def test_more_than_two_pallets_triggers_billing():
    stop = SortSegregateStop(sku_count=4, pallet_count=3, total_lines=4)
    assert calculate_sort_segregate_fee(stop) == Decimal("65.00")


def test_special_handling_makes_otherwise_small_stop_billable():
    stop = SortSegregateStop(sku_count=2, pallet_count=1, total_lines=2, fragile_lines=1)
    assert calculate_sort_segregate_fee(stop) == Decimal("65.00")


def test_customer_labels_waive_setup_charge():
    stop = SortSegregateStop(
        sku_count=8,
        pallet_count=2,
        total_lines=8,
        customer_labels_provided=True,
    )
    assert calculate_sort_segregate_fee(stop) == Decimal("65.00")


def test_started_half_hour_rounds_up():
    stop = SortSegregateStop(sku_count=15, pallet_count=2, total_lines=15)
    assert calculate_sort_segregate_fee(stop) == Decimal("65.00")


def test_majority_special_lines_add_complexity_surcharge():
    stop = SortSegregateStop(
        sku_count=6,
        pallet_count=2,
        total_lines=4,
        fragile_lines=2,
        hazmat_lines=1,
    )
    assert calculate_sort_segregate_fee(stop) == Decimal("78.00")


def test_exactly_half_special_lines_does_not_add_surcharge():
    stop = SortSegregateStop(
        sku_count=6,
        pallet_count=2,
        total_lines=4,
        fragile_lines=2,
        hazmat_lines=0,
    )
    assert calculate_sort_segregate_fee(stop) == Decimal("65.00")


def test_custom_terms_can_exceed_minimum_with_exact_computation():
    stop = SortSegregateStop(sku_count=18, pallet_count=5, total_lines=18, hazmat_lines=2)
    terms = SortSegregateTerms(hourly_rate=Decimal("60.00"), minimum_fee=Decimal("70.00"))
    assert calculate_sort_segregate_fee(stop, terms) == Decimal("150.00")


def test_invalid_special_lines_are_rejected():
    stop = SortSegregateStop(sku_count=3, pallet_count=1, total_lines=2, fragile_lines=2, hazmat_lines=1)
    with pytest.raises(ValueError):
        calculate_sort_segregate_fee(stop)
