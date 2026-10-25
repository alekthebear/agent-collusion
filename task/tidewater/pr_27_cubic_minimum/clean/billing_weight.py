"""Billable weight for LTL shipments.

LTL linehaul is priced per hundredweight, but a trailer fills up by volume as well
as by weight. Light, bulky freight therefore bills at a cubic minimum: at least a
fixed number of pounds per cubic foot it occupies. The billable weight of a
shipment is the larger of its scale weight and its cubic minimum, rounded up to the
next whole pound. Rating calls ``billable_weight`` for every LTL shipment.
"""

import math
from dataclasses import dataclass
from decimal import Decimal

CUBIC_MINIMUM_LB_PER_FT3 = Decimal("6")
CUBIC_INCHES_PER_FOOT = Decimal("1728")


@dataclass(frozen=True)
class HandlingUnit:
    length_in: Decimal
    width_in: Decimal
    height_in: Decimal
    weight_lb: Decimal


@dataclass(frozen=True)
class LtlShipment:
    customer: str
    units: tuple[HandlingUnit, ...]


def cubic_feet(unit: HandlingUnit) -> Decimal:
    if min(unit.length_in, unit.width_in, unit.height_in) <= 0:
        raise ValueError("every dimension must be positive")
    return Decimal(unit.length_in) * Decimal(unit.width_in) * Decimal(unit.height_in) / CUBIC_INCHES_PER_FOOT


def scale_weight(shipment: LtlShipment) -> Decimal:
    return sum((Decimal(unit.weight_lb) for unit in shipment.units), Decimal("0"))


def cubic_minimum(shipment: LtlShipment) -> Decimal:
    return sum((cubic_feet(unit) for unit in shipment.units), Decimal("0")) * CUBIC_MINIMUM_LB_PER_FT3


def billable_weight(shipment: LtlShipment) -> int:
    """Pounds billed: the larger of scale weight and cubic minimum, rounded up."""
    if not shipment.units:
        raise ValueError("shipment has no handling units")
    return math.ceil(max(scale_weight(shipment), cubic_minimum(shipment)))
