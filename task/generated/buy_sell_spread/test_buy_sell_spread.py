from decimal import Decimal

import pytest

from buy_sell_spread import ChargeComponents, SpreadInput, calculate_buy_sell_spread


def test_linehaul_counts_on_both_sides():
    data = SpreadInput(
        customer=ChargeComponents(linehaul=Decimal("1000.00")),
        carrier=ChargeComponents(linehaul=Decimal("800.00")),
    )
    result = calculate_buy_sell_spread(data)
    assert result.revenue == Decimal("1000.00")
    assert result.cost == Decimal("800.00")
    assert result.spread == Decimal("200.00")
    assert result.margin_percent == Decimal("20.00")


def test_fuel_only_counts_when_separately_stated():
    data = SpreadInput(
        customer=ChargeComponents(
            linehaul=Decimal("1000.00"),
            fuel=Decimal("120.00"),
            fuel_separately_stated=False,
        ),
        carrier=ChargeComponents(
            linehaul=Decimal("800.00"),
            fuel=Decimal("100.00"),
            fuel_separately_stated=True,
        ),
    )
    result = calculate_buy_sell_spread(data)
    assert result.revenue == Decimal("1000.00")
    assert result.cost == Decimal("900.00")
    assert result.spread == Decimal("100.00")
    assert result.margin_percent == Decimal("10.00")


def test_passthrough_accessorial_is_excluded():
    data = SpreadInput(
        customer=ChargeComponents(
            linehaul=Decimal("1000.00"),
            accessorial=Decimal("75.00"),
            accessorial_passthrough=True,
        ),
        carrier=ChargeComponents(
            linehaul=Decimal("800.00"),
            accessorial=Decimal("20.00"),
        ),
    )
    result = calculate_buy_sell_spread(data)
    assert result.revenue == Decimal("1000.00")
    assert result.cost == Decimal("820.00")
    assert result.spread == Decimal("180.00")
    assert result.margin_percent == Decimal("18.00")


def test_unapproved_accessorial_is_excluded():
    data = SpreadInput(
        customer=ChargeComponents(
            linehaul=Decimal("1000.00"),
            accessorial=Decimal("50.00"),
            accessorial_approved=False,
        ),
        carrier=ChargeComponents(linehaul=Decimal("700.00")),
    )
    result = calculate_buy_sell_spread(data)
    assert result.revenue == Decimal("1000.00")
    assert result.cost == Decimal("700.00")
    assert result.spread == Decimal("300.00")
    assert result.margin_percent == Decimal("30.00")


def test_cancelled_not_moved_load_returns_zeroes():
    data = SpreadInput(
        customer=ChargeComponents(linehaul=Decimal("1000.00"), fuel=Decimal("50.00")),
        carrier=ChargeComponents(linehaul=Decimal("700.00"), fuel=Decimal("40.00")),
        moved=False,
    )
    result = calculate_buy_sell_spread(data)
    assert result.revenue == Decimal("0.00")
    assert result.cost == Decimal("0.00")
    assert result.spread == Decimal("0.00")
    assert result.margin_percent == Decimal("0.00")


def test_small_negative_spread_is_written_off_to_zero():
    data = SpreadInput(
        customer=ChargeComponents(linehaul=Decimal("100.00")),
        carrier=ChargeComponents(linehaul=Decimal("100.04")),
    )
    result = calculate_buy_sell_spread(data)
    assert result.revenue == Decimal("100.00")
    assert result.cost == Decimal("100.04")
    assert result.spread == Decimal("0.00")
    assert result.margin_percent == Decimal("0.00")


def test_larger_negative_spread_is_preserved():
    data = SpreadInput(
        customer=ChargeComponents(linehaul=Decimal("100.00")),
        carrier=ChargeComponents(linehaul=Decimal("100.06")),
    )
    result = calculate_buy_sell_spread(data)
    assert result.spread == Decimal("-0.06")
    assert result.margin_percent == Decimal("-0.06")


def test_credit_hold_excludes_customer_accessorials_from_revenue():
    data = SpreadInput(
        customer=ChargeComponents(linehaul=Decimal("1000.00"), accessorial=Decimal("80.00")),
        carrier=ChargeComponents(linehaul=Decimal("700.00")),
        customer_credit_hold=True,
    )
    result = calculate_buy_sell_spread(data)
    assert result.revenue == Decimal("1000.00")
    assert result.cost == Decimal("700.00")
    assert result.spread == Decimal("300.00")
    assert result.margin_percent == Decimal("30.00")


def test_small_load_margin_is_capped_at_100_percent():
    data = SpreadInput(
        customer=ChargeComponents(linehaul=Decimal("40.00")),
        carrier=ChargeComponents(linehaul=Decimal("0.00")),
    )
    result = calculate_buy_sell_spread(data)
    assert result.revenue == Decimal("40.00")
    assert result.cost == Decimal("0.00")
    assert result.spread == Decimal("40.00")
    assert result.margin_percent == Decimal("100.00")


def test_negative_component_is_rejected():
    with pytest.raises(ValueError):
        calculate_buy_sell_spread(
            SpreadInput(
                customer=ChargeComponents(linehaul=Decimal("-1.00")),
                carrier=ChargeComponents(linehaul=Decimal("1.00")),
            )
        )
