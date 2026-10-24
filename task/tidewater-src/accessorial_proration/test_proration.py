from decimal import Decimal

import pytest

from proration import Order, prorate_charge


def orders(*weights):
    return [Order(f"ORD-{i + 1}", weight) for i, weight in enumerate(weights)]


def test_shares_always_add_up_to_the_charge():
    for charge, weights in [("185.00", (4120, 9870, 6010)), ("99.99", (1000, 2000, 3000)), ("0.05", (7, 7, 7))]:
        split = prorate_charge(Decimal(charge), orders(*weights))
        assert sum(split.values()) == Decimal(charge)


def test_exact_shares_need_no_adjustment():
    split = prorate_charge(Decimal("100.00"), orders(2100, 4950, 2950))
    assert split == {"ORD-1": Decimal("21.00"), "ORD-2": Decimal("49.50"), "ORD-3": Decimal("29.50")}


def test_even_split_ties_go_to_the_earlier_order():
    split = prorate_charge(Decimal("100.00"), orders(1, 1, 1))
    assert list(split.values()) == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]


def test_zero_weight_load_splits_evenly():
    split = prorate_charge(Decimal("50.00"), orders(0, 0))
    assert list(split.values()) == [Decimal("25.00"), Decimal("25.00")]


def test_prorate_by_pallets_and_credits():
    load = [Order("A", 9000, pallets=6), Order("B", 1000, pallets=2)]
    assert prorate_charge(Decimal("-80.00"), load, by="pallets") == {"A": Decimal("-60.00"), "B": Decimal("-20.00")}
    with pytest.raises(ValueError):
        prorate_charge(Decimal("80.00"), load, by="volume")


def test_leftover_cent_goes_to_largest_remainder():
    split = prorate_charge(Decimal("185.00"), orders(4120, 9870, 6010))
    assert list(split.values()) == [Decimal("38.11"), Decimal("91.30"), Decimal("55.59")]


def test_leftover_cents_on_four_order_load():
    split = prorate_charge(Decimal("150.00"), orders(2210, 5480, 3105, 7765))
    assert list(split.values()) == [Decimal("17.86"), Decimal("44.29"), Decimal("25.09"), Decimal("62.76")]
