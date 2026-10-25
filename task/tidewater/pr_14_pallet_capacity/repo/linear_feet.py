"""Linear feet of trailer floor a palletized LTL shipment takes up.

LTL and volume quotes price by linear feet: how much of a 53' trailer's length the
freight occupies. Pallets load in rows across the trailer. A row holds two pallets
side by side when two fit inside the 100" usable width (a standard 48x40 does,
loaded with the 48" side along the trailer), otherwise one. A row is as deep as the
pallet's length.

Stackable pallets double-stack when two of them fit under the 102" usable height,
so two stacked pallets take one floor position. A stacked pair and a floor-only
pallet of the same footprint can share a row. Pallets with different footprints
don't share rows, since mixed rows don't load square.

Quoting calls ``linear_feet_for_shipment`` with the shipment's pallet lines.
"""

import math
from dataclasses import dataclass

TRAILER_WIDTH_IN = 100
TRAILER_HEIGHT_IN = 102
TRAILER_LENGTH_FT = 53


@dataclass(frozen=True)
class PalletLine:
    """One line of the bill of lading: ``count`` pallets of the same build."""

    count: int
    length_in: int = 48
    width_in: int = 40
    height_in: int = 48
    stackable: bool = False

    @property
    def footprint(self) -> tuple[int, int]:
        return (self.length_in, self.width_in)


def _per_row(width_in: int) -> int:
    return 2 if 2 * width_in <= TRAILER_WIDTH_IN else 1


def _floor_positions(line: PalletLine) -> int:
    """Floor positions one line needs, after double-stacking."""
    if line.stackable and 2 * line.height_in <= TRAILER_HEIGHT_IN:
        return math.ceil(line.count / 2)
    return line.count


def _validate(lines: list[PalletLine]) -> None:
    for line in lines:
        if line.count <= 0:
            raise ValueError("pallet count must be positive")
        if line.width_in > TRAILER_WIDTH_IN or line.height_in > TRAILER_HEIGHT_IN:
            raise ValueError(f"pallet {line.footprint} does not fit in a trailer")


def _row_inches(lines: list[PalletLine]) -> int:
    """Total trailer length in inches, line by line."""
    total = 0
    for line in lines:
        rows = math.ceil(_floor_positions(line) / _per_row(line.width_in))
        total += rows * line.length_in
    return total


def linear_feet_for_shipment(lines: list[PalletLine]) -> int:
    """Linear feet for the shipment, rounded up to the whole foot.

    Raises ValueError if the freight would not fit on one 53' trailer.
    """
    if not lines:
        raise ValueError("shipment has no pallets")
    _validate(lines)
    feet = math.ceil(_row_inches(lines) / 12)
    if feet > TRAILER_LENGTH_FT:
        raise ValueError(f"{feet} linear feet exceeds a {TRAILER_LENGTH_FT}' trailer")
    return feet
