"""Dimensional billed weight for parcel and LTL rating.

Tidewater rates many lightweight shipments on dimensional weight rather than actual
scale weight. The cube is measured from entered dimensions, then divided by a
mode-specific divisor to produce a dimensional weight. Parcel and LTL contracts
differ in how they round dimensions and pounds, and some shipments are forced
back to actual weight.

Business rules implemented here:
- Any non-positive length, width, height, or actual weight is invalid.
- Parcel dimensions are measured from the entered decimal inches, with any side below
  1 inch treated as 1 inch for rating.
- LTL dimensions are measured to the nearest whole inch with .5 rounding up, but any
  side below 1 inch is still treated as 1 inch.
- Dimensional billing applies only when the measured cube is at least 1,728 cubic
  inches (one cubic foot). Smaller pieces bill at actual weight.
- Parcel uses divisor 139 for domestic and 166 for export. LTL uses divisor 194.
- Parcel dimensional pounds are rounded up to the next whole pound.
- LTL dimensional pounds are rounded to the nearest half pound, then the billed weight
  rounds up to the next whole pound.
- A package marked tube is not dimensionally rated in parcel mode and bills at actual
  weight. In LTL, tubes still rate dimensionally.
- Actual weight bills to the next whole pound.
- The final billed weight is the greater of dimensional and actual billing weights.
"""

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

ONE = Decimal("1")
HALF = Decimal("0.5")
CUBIC_INCH_THRESHOLD = 1728


@dataclass(frozen=True)
class ShipmentDimensions:
    length_in: Decimal
    width_in: Decimal
    height_in: Decimal
    actual_weight_lb: Decimal
    mode: str = "parcel"
    service: str = "domestic"
    package_type: str = "carton"


def _validate(shipment: ShipmentDimensions) -> None:
    if shipment.mode not in {"parcel", "ltl"}:
        raise ValueError(f"unsupported mode {shipment.mode}")
    if shipment.service not in {"domestic", "export"}:
        raise ValueError(f"unsupported service {shipment.service}")
    for name, value in {
        "length_in": shipment.length_in,
        "width_in": shipment.width_in,
        "height_in": shipment.height_in,
        "actual_weight_lb": shipment.actual_weight_lb,
    }.items():
        if value <= 0:
            raise ValueError(f"{name} must be positive, got {value}")


def _round_side(value: Decimal, mode: str) -> Decimal:
    value = value if value >= ONE else ONE
    if mode == "ltl":
        return value.quantize(ONE, rounding=ROUND_HALF_UP)
    return value


def _measured_cube(shipment: ShipmentDimensions) -> Decimal:
    return (
        _round_side(shipment.length_in, shipment.mode)
        * _round_side(shipment.width_in, shipment.mode)
        * _round_side(shipment.height_in, shipment.mode)
    )


def _divisor(shipment: ShipmentDimensions) -> int:
    if shipment.mode == "ltl":
        return 194
    return 166 if shipment.service == "export" else 139


def _actual_billing_weight(shipment: ShipmentDimensions) -> Decimal:
    return shipment.actual_weight_lb.quantize(ONE, rounding=ROUND_CEILING)


def _dimensional_weight(cube: Decimal, shipment: ShipmentDimensions) -> Decimal:
    raw = cube / Decimal(_divisor(shipment))
    if shipment.mode == "parcel":
        return raw.quantize(ONE, rounding=ROUND_CEILING)
    half_steps = (raw * 2).quantize(ONE, rounding=ROUND_HALF_UP) / 2
    return half_steps.quantize(ONE, rounding=ROUND_CEILING)


def calculate_dimensional_weight(shipment: ShipmentDimensions) -> Decimal:
    """Return billed weight in whole pounds.

    The result is the greater of actual billing weight and dimensional billing weight,
    unless dimensional rules are bypassed by threshold or package type.
    """
    _validate(shipment)
    actual = _actual_billing_weight(shipment)
    if shipment.mode == "parcel" and shipment.package_type == "tube":
        return actual
    cube = _measured_cube(shipment)
    if cube < CUBIC_INCH_THRESHOLD:
        return actual
    dim = _dimensional_weight(cube, shipment)
    return dim if dim > actual else actual
