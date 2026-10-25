from decimal import Decimal

import pytest

from cost_plus_price import PricingPolicy, QuoteCost, calculate_cost_plus_price


def test_uses_carrier_cost_by_default_even_when_modeled_present():
    quote = QuoteCost(carrier_cost=Decimal("400.00"), modeled_cost=Decimal("700.00"))
    assert calculate_cost_plus_price(quote) == Decimal("472.00")


def test_can_prefer_modeled_cost_when_configured():
    quote = QuoteCost(carrier_cost=Decimal("400.00"), modeled_cost=Decimal("700.00"))
    policy = PricingPolicy(use_modeled_when_present=True)
    assert calculate_cost_plus_price(quote, policy) == Decimal("784.00")


def test_fuel_and_accessorials_are_included_by_default():
    quote = QuoteCost(
        carrier_cost=Decimal("450.00"),
        fuel_surcharge=Decimal("25.00"),
        accessorials=Decimal("30.00"),
    )
    assert calculate_cost_plus_price(quote) == Decimal("565.60")


def test_policy_can_exclude_fuel_and_accessorials_from_pricing_base():
    quote = QuoteCost(
        carrier_cost=Decimal("450.00"),
        fuel_surcharge=Decimal("25.00"),
        accessorials=Decimal("30.00"),
    )
    policy = PricingPolicy(include_fuel=False, include_accessorials=False)
    assert calculate_cost_plus_price(quote, policy) == Decimal("531.00")


def test_breakpoints_are_inclusive_at_500_and_1500():
    low = QuoteCost(carrier_cost=Decimal("500.00"))
    mid = QuoteCost(carrier_cost=Decimal("1500.00"))
    assert calculate_cost_plus_price(low) == Decimal("590.00")
    assert calculate_cost_plus_price(mid) == Decimal("1680.00")


def test_cost_above_mid_break_gets_high_markup():
    quote = QuoteCost(carrier_cost=Decimal("1500.01"))
    assert calculate_cost_plus_price(quote) == Decimal("1620.01")


def test_fixed_margin_adder_overrides_percentage_markup():
    quote = QuoteCost(carrier_cost=Decimal("1000.00"))
    policy = PricingPolicy(fixed_margin_adder=Decimal("90.00"))
    assert calculate_cost_plus_price(quote, policy) == Decimal("1090.00")


def test_expedited_adds_surcharge_to_margin():
    quote = QuoteCost(carrier_cost=Decimal("1000.00"), expedited=True)
    assert calculate_cost_plus_price(quote) == Decimal("1195.00")


def test_minimum_margin_applies_when_fixed_adder_is_too_small():
    quote = QuoteCost(carrier_cost=Decimal("200.00"))
    policy = PricingPolicy(fixed_margin_adder=Decimal("10.00"), minimum_margin=Decimal("35.00"))
    assert calculate_cost_plus_price(quote, policy) == Decimal("235.00")


def test_negative_values_and_missing_cost_are_rejected():
    with pytest.raises(ValueError):
        calculate_cost_plus_price(QuoteCost())
    with pytest.raises(ValueError):
        calculate_cost_plus_price(QuoteCost(carrier_cost=Decimal("-1.00")))
