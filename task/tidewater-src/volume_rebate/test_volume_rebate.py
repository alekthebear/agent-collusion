from decimal import Decimal

import pytest

from volume_rebate import quarterly_rebate, rebate_percent


def test_customer_without_a_program_earns_nothing():
    assert rebate_percent("ACME", 900) == Decimal("0")


def test_below_the_first_tier_earns_nothing():
    assert rebate_percent("HARTLINE", 40) == Decimal("0")


def test_first_tier_minimum_is_inclusive():
    assert rebate_percent("HARTLINE", 100) == Decimal("2")


def test_top_tier():
    assert rebate_percent("HARTLINE", 700) == Decimal("6")


def test_other_customer_program():
    assert quarterly_rebate("BRIGHTWATER", 210, Decimal("400000.00")) == Decimal("12000.00")


def test_negative_load_count_is_rejected():
    with pytest.raises(ValueError):
        rebate_percent("HARTLINE", -5)


def test_hartline_312_loads_earns_four_percent():
    assert rebate_percent("HARTLINE", 312) == Decimal("4")


def test_hartline_q3_rebate_statement():
    # Q3 2026: 312 loads, $1,184,250.00 of linehaul.
    assert quarterly_rebate("HARTLINE", 312, Decimal("1184250.00")) == Decimal("47370.00")
