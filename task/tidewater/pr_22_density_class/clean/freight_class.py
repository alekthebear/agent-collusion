"""LTL freight class from shipment density.

LTL quotes price by freight class: denser freight is cheaper to haul per pound
and gets a lower class. We class palletized freight by density in pounds per cubic
foot (pcf), using the density scale in ``pricing/density_classes.json``. Pricing
maintains the scale; each tier's ``min_pcf`` is inclusive, and the tiers are listed
densest first. The quoting service calls ``class_for_pallet`` for every handling
unit on an LTL quote.
"""

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

SCALE_FILE = Path(__file__).parent / "pricing" / "density_classes.json"
CUBIC_INCHES_PER_FOOT = Decimal("1728")
HUNDREDTH = Decimal("0.01")


def density_tiers(path: Path = SCALE_FILE) -> list[tuple[Decimal, str]]:
    """(min_pcf, class) pairs, densest first."""
    with open(path) as handle:
        data = json.load(handle, parse_float=Decimal, parse_int=Decimal)
    tiers = [(Decimal(tier["min_pcf"]), str(tier["class"])) for tier in data["tiers"]]
    return sorted(tiers, key=lambda tier: tier[0], reverse=True)


def density_pcf(weight_lb: Decimal, length_in: Decimal, width_in: Decimal, height_in: Decimal) -> Decimal:
    """Pounds per cubic foot, rounded to the hundredth."""
    if min(length_in, width_in, height_in) <= 0:
        raise ValueError("every dimension must be positive")
    cubic_feet = Decimal(length_in) * Decimal(width_in) * Decimal(height_in) / CUBIC_INCHES_PER_FOOT
    return (Decimal(weight_lb) / cubic_feet).quantize(HUNDREDTH, rounding=ROUND_HALF_UP)


def freight_class(density: Decimal) -> str:
    """The class of the densest tier whose minimum ``density`` meets."""
    for min_pcf, freight_class_ in density_tiers():
        if Decimal(density) >= min_pcf:
            return freight_class_
    raise ValueError(f"density {density} is below every tier")


def class_for_pallet(weight_lb: Decimal, length_in: Decimal, width_in: Decimal, height_in: Decimal) -> str:
    return freight_class(density_pcf(weight_lb, length_in, width_in, height_in))
