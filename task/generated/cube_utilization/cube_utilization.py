"""Trailer cube utilization for planning and settlement review.

Operations compares booked freight volume against the usable interior cube of the
trailer. The usable cube starts from the equipment's interior dimensions, then may
be reduced for decking, load bars, or other reserved space. Freight cube is based
on each item's dimensions and piece count. Non-stackable freight consumes full
height lanes, while stackable freight can use only its own cube.

Business rules used by Tidewater planners:
- Dimensions are entered in inches; cube is computed in cubic feet.
- Each line rounds its own raw cube to 0.01 cubic feet using half-up rounding.
- A line marked non_stackable consumes a floor footprint times the full usable
  trailer height, not the freight's actual height.
- If a line's actual height exceeds usable trailer height, that line is treated as
  overheight and still consumes full-height cube plus a 10% planning penalty.
- Reserved space is subtracted from equipment cube before utilization is measured,
  but never below zero.
- Utilization percent is freight cube divided by usable equipment cube, rounded to
  0.1%. If usable equipment cube is zero, utilization is 0.0 when freight is zero
  and 100.0 when freight exists.
- Remaining cube is usable equipment cube minus freight cube, floored at zero and
  rounded to 0.01.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENTI_CUBE = Decimal("0.01")
TENTH_PERCENT = Decimal("0.1")
CUBIC_INCHES_PER_FOOT = Decimal("1728")
OVERHEIGHT_PENALTY = Decimal("1.10")


@dataclass(frozen=True)
class EquipmentDimensions:
    interior_length_in: Decimal
    interior_width_in: Decimal
    interior_height_in: Decimal
    reserved_cube_ft3: Decimal = Decimal("0.00")


@dataclass(frozen=True)
class ShipmentLine:
    pieces: int
    length_in: Decimal
    width_in: Decimal
    height_in: Decimal
    stackable: bool = True


@dataclass(frozen=True)
class CubeUtilization:
    freight_cube_ft3: Decimal
    usable_cube_ft3: Decimal
    remaining_cube_ft3: Decimal
    utilization_percent: Decimal


def _q(value: Decimal, places: Decimal) -> Decimal:
    return value.quantize(places, rounding=ROUND_HALF_UP)


def _validate_equipment(equipment: EquipmentDimensions) -> None:
    dims = (
        equipment.interior_length_in,
        equipment.interior_width_in,
        equipment.interior_height_in,
    )
    if any(d <= 0 for d in dims):
        raise ValueError("equipment interior dimensions must be positive")
    if equipment.reserved_cube_ft3 < 0:
        raise ValueError("reserved cube cannot be negative")


def _validate_line(line: ShipmentLine) -> None:
    if line.pieces < 0:
        raise ValueError("pieces cannot be negative")
    dims = (line.length_in, line.width_in, line.height_in)
    if line.pieces and any(d <= 0 for d in dims):
        raise ValueError("shipment dimensions must be positive when pieces are present")


def _equipment_cube(equipment: EquipmentDimensions) -> Decimal:
    gross = (
        equipment.interior_length_in
        * equipment.interior_width_in
        * equipment.interior_height_in
        / CUBIC_INCHES_PER_FOOT
    )
    usable = gross - equipment.reserved_cube_ft3
    return _q(usable if usable > 0 else Decimal("0.00"), CENTI_CUBE)


def _line_cube(line: ShipmentLine, usable_height_in: Decimal) -> Decimal:
    if line.pieces == 0:
        return Decimal("0.00")
    footprint = line.length_in * line.width_in
    if line.stackable:
        raw = footprint * line.height_in * line.pieces / CUBIC_INCHES_PER_FOOT
        return _q(raw, CENTI_CUBE)
    consumed_height = usable_height_in
    raw = footprint * consumed_height * line.pieces / CUBIC_INCHES_PER_FOOT
    if line.height_in > usable_height_in:
        raw *= OVERHEIGHT_PENALTY
    return _q(raw, CENTI_CUBE)


def _utilization_percent(freight_cube: Decimal, usable_cube: Decimal) -> Decimal:
    if usable_cube == 0:
        return Decimal("100.0") if freight_cube > 0 else Decimal("0.0")
    return _q(freight_cube * Decimal("100") / usable_cube, TENTH_PERCENT)


def calculate_cube_utilization(
    equipment: EquipmentDimensions, lines: list[ShipmentLine]
) -> CubeUtilization:
    """Compute used cube, remaining cube, and utilization percentage.

    >>> eq = EquipmentDimensions(Decimal("636"), Decimal("100"), Decimal("110"))
    >>> lines = [ShipmentLine(1, Decimal("48"), Decimal("40"), Decimal("50"))]
    >>> calculate_cube_utilization(eq, lines).freight_cube_ft3
    Decimal('55.56')
    """
    _validate_equipment(equipment)
    freight_cube = Decimal("0.00")
    for line in lines:
        _validate_line(line)
        freight_cube += _line_cube(line, equipment.interior_height_in)
    freight_cube = _q(freight_cube, CENTI_CUBE)
    usable_cube = _equipment_cube(equipment)
    remaining = usable_cube - freight_cube
    remaining_cube = _q(remaining if remaining > 0 else Decimal("0.00"), CENTI_CUBE)
    utilization = _utilization_percent(freight_cube, usable_cube)
    return CubeUtilization(
        freight_cube_ft3=freight_cube,
        usable_cube_ft3=usable_cube,
        remaining_cube_ft3=remaining_cube,
        utilization_percent=utilization,
    )
