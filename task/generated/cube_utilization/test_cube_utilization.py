from decimal import Decimal

import pytest

from cube_utilization import (
    EquipmentDimensions,
    ShipmentLine,
    calculate_cube_utilization,
)


def test_stackable_line_uses_its_own_cube():
    equipment = EquipmentDimensions(Decimal("636"), Decimal("100"), Decimal("110"))
    lines = [ShipmentLine(1, Decimal("48"), Decimal("40"), Decimal("50"), True)]
    result = calculate_cube_utilization(equipment, lines)
    assert result.freight_cube_ft3 == Decimal("55.56")
    assert result.usable_cube_ft3 == Decimal("4048.61")
    assert result.remaining_cube_ft3 == Decimal("3993.05")
    assert result.utilization_percent == Decimal("1.4")


def test_non_stackable_line_consumes_full_trailer_height():
    equipment = EquipmentDimensions(Decimal("636"), Decimal("100"), Decimal("110"))
    lines = [ShipmentLine(1, Decimal("48"), Decimal("40"), Decimal("50"), False)]
    result = calculate_cube_utilization(equipment, lines)
    assert result.freight_cube_ft3 == Decimal("122.22")
    assert result.utilization_percent == Decimal("3.0")


def test_overheight_non_stackable_gets_penalty():
    equipment = EquipmentDimensions(Decimal("636"), Decimal("100"), Decimal("110"))
    lines = [ShipmentLine(1, Decimal("48"), Decimal("40"), Decimal("120"), False)]
    result = calculate_cube_utilization(equipment, lines)
    assert result.freight_cube_ft3 == Decimal("134.44")
    assert result.utilization_percent == Decimal("3.3")


def test_reserved_cube_reduces_usable_capacity():
    equipment = EquipmentDimensions(
        Decimal("636"), Decimal("100"), Decimal("110"), reserved_cube_ft3=Decimal("48.61")
    )
    lines = []
    result = calculate_cube_utilization(equipment, lines)
    assert result.usable_cube_ft3 == Decimal("4000.00")
    assert result.remaining_cube_ft3 == Decimal("4000.00")
    assert result.utilization_percent == Decimal("0.0")


def test_reserved_cube_cannot_drive_usable_below_zero():
    equipment = EquipmentDimensions(
        Decimal("100"), Decimal("100"), Decimal("100"), reserved_cube_ft3=Decimal("1000.00")
    )
    result = calculate_cube_utilization(equipment, [])
    assert result.usable_cube_ft3 == Decimal("0.00")
    assert result.remaining_cube_ft3 == Decimal("0.00")
    assert result.utilization_percent == Decimal("0.0")


def test_zero_usable_cube_with_freight_reports_full_utilization():
    equipment = EquipmentDimensions(
        Decimal("100"), Decimal("100"), Decimal("100"), reserved_cube_ft3=Decimal("1000.00")
    )
    lines = [ShipmentLine(1, Decimal("10"), Decimal("10"), Decimal("10"), True)]
    result = calculate_cube_utilization(equipment, lines)
    assert result.freight_cube_ft3 == Decimal("0.58")
    assert result.utilization_percent == Decimal("100.0")


def test_zero_piece_line_contributes_no_cube():
    equipment = EquipmentDimensions(Decimal("636"), Decimal("100"), Decimal("110"))
    lines = [ShipmentLine(0, Decimal("48"), Decimal("40"), Decimal("50"), False)]
    result = calculate_cube_utilization(equipment, lines)
    assert result.freight_cube_ft3 == Decimal("0.00")
    assert result.remaining_cube_ft3 == Decimal("4048.61")


def test_multiple_lines_sum_each_line_after_individual_rounding():
    equipment = EquipmentDimensions(Decimal("200"), Decimal("100"), Decimal("100"))
    lines = [
        ShipmentLine(3, Decimal("13"), Decimal("13"), Decimal("13"), True),
        ShipmentLine(2, Decimal("20"), Decimal("20"), Decimal("20"), True),
    ]
    result = calculate_cube_utilization(equipment, lines)
    assert result.freight_cube_ft3 == Decimal("13.07")
    assert result.usable_cube_ft3 == Decimal("1157.41")
    assert result.utilization_percent == Decimal("1.1")


def test_negative_pieces_are_rejected():
    equipment = EquipmentDimensions(Decimal("636"), Decimal("100"), Decimal("110"))
    with pytest.raises(ValueError):
        calculate_cube_utilization(
            equipment,
            [ShipmentLine(-1, Decimal("48"), Decimal("40"), Decimal("50"), True)],
        )


def test_nonzero_pieces_require_positive_dimensions():
    equipment = EquipmentDimensions(Decimal("636"), Decimal("100"), Decimal("110"))
    with pytest.raises(ValueError):
        calculate_cube_utilization(
            equipment,
            [ShipmentLine(1, Decimal("0"), Decimal("40"), Decimal("50"), True)],
        )
