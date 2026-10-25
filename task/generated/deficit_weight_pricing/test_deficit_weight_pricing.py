from decimal import Decimal

import pytest

from deficit_weight_pricing import (
    DeficitPricingInput,
    WeightBreak,
    calculate_deficit_weight_pricing,
)


BREAKS = (
    WeightBreak(1, Decimal("22.40")),
    WeightBreak(500, Decimal("18.10")),
    WeightBreak(1000, Decimal("14.20")),
    WeightBreak(2000, Decimal("11.60")),
)


def test_uses_deficit_when_next_break_lowers_total_charge():
    data = DeficitPricingInput(actual_weight=480, breaks=BREAKS)
    assert calculate_deficit_weight_pricing(data) == Decimal("90.50")


def test_uses_deficit_at_higher_break_when_it_lowers_total_charge():
    data = DeficitPricingInput(actual_weight=990, breaks=BREAKS)
    assert calculate_deficit_weight_pricing(data) == Decimal("142.00")


def test_exact_break_weight_has_no_deficit():
    data = DeficitPricingInput(actual_weight=1000, breaks=BREAKS)
    assert calculate_deficit_weight_pricing(data) == Decimal("142.00")


def test_density_exempt_disallows_deficit_pricing():
    data = DeficitPricingInput(actual_weight=990, breaks=BREAKS, density_exempt=True)
    assert calculate_deficit_weight_pricing(data) == Decimal("179.19")


def test_gap_above_max_deficit_disallows_deficit():
    data = DeficitPricingInput(actual_weight=1401, breaks=BREAKS, max_deficit_pounds=498)
    assert calculate_deficit_weight_pricing(data) == Decimal("198.94")


def test_gap_equal_to_max_deficit_still_requires_lower_total():
    data = DeficitPricingInput(actual_weight=1401, breaks=BREAKS, max_deficit_pounds=599)
    assert calculate_deficit_weight_pricing(data) == Decimal("198.94")


def test_last_break_cannot_deficit_to_nonexistent_break():
    data = DeficitPricingInput(actual_weight=2500, breaks=BREAKS)
    assert calculate_deficit_weight_pricing(data) == Decimal("290.00")


def test_rounds_half_up_to_cents():
    custom_breaks = (
        WeightBreak(1, Decimal("10.005")),
        WeightBreak(500, Decimal("9.000")),
    )
    data = DeficitPricingInput(actual_weight=100, breaks=custom_breaks)
    assert calculate_deficit_weight_pricing(data) == Decimal("10.01")


def test_unsorted_breaks_are_rejected():
    bad_breaks = (
        WeightBreak(500, Decimal("18.10")),
        WeightBreak(1, Decimal("22.40")),
    )
    with pytest.raises(ValueError):
        calculate_deficit_weight_pricing(DeficitPricingInput(actual_weight=300, breaks=bad_breaks))


def test_nonpositive_weight_is_rejected():
    with pytest.raises(ValueError):
        calculate_deficit_weight_pricing(DeficitPricingInput(actual_weight=0, breaks=BREAKS))
