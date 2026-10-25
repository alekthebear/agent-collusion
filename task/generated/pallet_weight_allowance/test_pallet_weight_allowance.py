from decimal import Decimal

import pytest

from pallet_weight_allowance import (
    PalletLoad,
    WeightAllowance,
    calculate_pallet_weight_allowance,
)


def test_zero_pallets_produce_no_allowance():
    load = PalletLoad(gross_weight_lb=Decimal("1200"), pallet_count=0, pallet_style="wood")
    assert calculate_pallet_weight_allowance(load) == WeightAllowance(
        allowance_lb=Decimal("0"), net_weight_lb=Decimal("1200")
    )


def test_standard_wood_schedule_is_capped_for_general_freight():
    load = PalletLoad(gross_weight_lb=Decimal("2000"), pallet_count=4, pallet_style="wood", commodity="general")
    assert calculate_pallet_weight_allowance(load) == WeightAllowance(
        allowance_lb=Decimal("160"), net_weight_lb=Decimal("1840")
    )


def test_plastic_tare_rounds_half_up_to_whole_pound():
    load = PalletLoad(gross_weight_lb=Decimal("1000"), pallet_count=1, pallet_style="plastic", commodity="food")
    assert calculate_pallet_weight_allowance(load) == WeightAllowance(
        allowance_lb=Decimal("49"), net_weight_lb=Decimal("951")
    )


def test_small_load_gets_ten_percent_handling_bump():
    load = PalletLoad(gross_weight_lb=Decimal("499"), pallet_count=2, pallet_style="wood", commodity="food")
    assert calculate_pallet_weight_allowance(load) == WeightAllowance(
        allowance_lb=Decimal("88"), net_weight_lb=Decimal("411")
    )


def test_five_hundred_pound_boundary_does_not_get_bump():
    load = PalletLoad(gross_weight_lb=Decimal("500"), pallet_count=2, pallet_style="wood", commodity="food")
    assert calculate_pallet_weight_allowance(load) == WeightAllowance(
        allowance_lb=Decimal("80"), net_weight_lb=Decimal("420")
    )


def test_commodity_cap_limits_dense_metal_load():
    load = PalletLoad(gross_weight_lb=Decimal("1000"), pallet_count=10, pallet_style="wood", commodity="metal")
    assert calculate_pallet_weight_allowance(load) == WeightAllowance(
        allowance_lb=Decimal("60"), net_weight_lb=Decimal("940")
    )


def test_slip_sheet_uses_special_two_percent_cap():
    load = PalletLoad(gross_weight_lb=Decimal("600"), pallet_count=10, pallet_style="slip_sheet", commodity="food")
    assert calculate_pallet_weight_allowance(load) == WeightAllowance(
        allowance_lb=Decimal("30"), net_weight_lb=Decimal("570")
    )


def test_mixed_style_requires_average_tare_within_range():
    with pytest.raises(ValueError):
        calculate_pallet_weight_allowance(
            PalletLoad(gross_weight_lb=Decimal("1500"), pallet_count=5, pallet_style="mixed", mixed_average_tare_lb=Decimal("19"))
        )


def test_mixed_style_uses_supplied_average_tare_and_cap():
    load = PalletLoad(
        gross_weight_lb=Decimal("1500"),
        pallet_count=3,
        pallet_style="mixed",
        mixed_average_tare_lb=Decimal("42.4"),
        commodity="general",
    )
    assert calculate_pallet_weight_allowance(load) == WeightAllowance(
        allowance_lb=Decimal("127"), net_weight_lb=Decimal("1373")
    )


def test_allowance_cannot_reduce_net_below_one_pound():
    load = PalletLoad(gross_weight_lb=Decimal("30"), pallet_count=1, pallet_style="wood", commodity="food")
    assert calculate_pallet_weight_allowance(load) == WeightAllowance(
        allowance_lb=Decimal("29"), net_weight_lb=Decimal("1")
    )
