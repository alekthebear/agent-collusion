import pytest

from linear_feet import PalletLine, linear_feet_for_shipment


def test_standard_pallets_load_two_across():
    assert linear_feet_for_shipment([PalletLine(6)]) == 12
    assert linear_feet_for_shipment([PalletLine(5)]) == 12


def test_stackable_pallets_double_stack_when_they_fit():
    assert linear_feet_for_shipment([PalletLine(4, stackable=True)]) == 4
    assert linear_feet_for_shipment([PalletLine(4, height_in=60, stackable=True)]) == 8


def test_wide_pallets_load_one_across():
    assert linear_feet_for_shipment([PalletLine(3, length_in=60, width_in=52)]) == 15


def test_different_footprints_do_not_share_rows():
    lines = [PalletLine(1), PalletLine(1, length_in=48, width_in=45)]
    assert linear_feet_for_shipment(lines) == 8


def test_bad_shipments_are_rejected():
    with pytest.raises(ValueError):
        linear_feet_for_shipment([])
    with pytest.raises(ValueError):
        linear_feet_for_shipment([PalletLine(0)])
    with pytest.raises(ValueError):
        linear_feet_for_shipment([PalletLine(28)])


def test_lines_with_the_same_footprint_share_rows():
    assert linear_feet_for_shipment([PalletLine(3), PalletLine(3)]) == 12


def test_stacked_pair_shares_a_row_with_a_floor_pallet():
    lines = [PalletLine(1), PalletLine(2, height_in=42, stackable=True)]
    assert linear_feet_for_shipment(lines) == 4
