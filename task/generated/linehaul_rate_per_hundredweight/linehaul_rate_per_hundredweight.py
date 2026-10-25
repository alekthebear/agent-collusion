"""Linehaul rate per hundredweight under common LTL tariff rules.

The rating service uses this helper to determine the effective per-CWT linehaul rate
for one shipment line before fuel and accessorials. Rates are quoted by freight class
and weight break. The selected rate may change under deficit rating when a shipment is
just short of the next break and paying the lower next-break rate on the higher minimum
weight would produce a lower charge. A shipment is still subject to a shipment minimum
charge after discount.

Business rules implemented here:
- Weight breaks are based on billed weight in pounds: under 500, 500-999, 1,000-1,999,
  2,000-4,999, and 5,000+.
- Base class rates are dollars per CWT before discount.
- Contract discount reduces the class rate but never below zero.
- Alaska and Hawaii service uses a 12% remote-area uplift after discount.
- Fragile freight class 125 and higher gets a 3% handling uplift unless the weight is
  2,000 pounds or more.
- Deficit rating is considered only when the shipment is within 150 pounds of the next
  break and only if the recomputed next-break charge is lower than the normal charge.
- Final linehaul charge cannot be below the shipment minimum charge.
- The function returns the effective rate per CWT as charge divided by actual billed
  weight in CWT, rounded half up to the cent.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
HUNDRED = Decimal("100")
REMOTE_UPLIFT = Decimal("0.12")
FRAGILE_UPLIFT = Decimal("0.03")
DEFICIT_WINDOW_LB = 150
MIN_CHARGE = Decimal("85.00")

_RATE_TABLE = {
    50: (Decimal("32.40"), Decimal("28.10"), Decimal("24.80"), Decimal("21.90"), Decimal("19.75")),
    70: (Decimal("38.60"), Decimal("33.70"), Decimal("29.50"), Decimal("25.90"), Decimal("23.10")),
    92: (Decimal("45.20"), Decimal("39.40"), Decimal("34.10"), Decimal("29.80"), Decimal("26.40")),
    125: (Decimal("57.80"), Decimal("50.10"), Decimal("43.30"), Decimal("37.60"), Decimal("33.20")),
}

_BREAKS = (1, 500, 1000, 2000, 5000)


@dataclass(frozen=True)
class LinehaulShipment:
    billed_weight_lb: int
    freight_class: int
    origin_state: str
    destination_state: str
    discount_percent: Decimal = Decimal("0")
    minimum_charge: Decimal = MIN_CHARGE


@dataclass(frozen=True)
class WeightRate:
    minimum_weight_lb: int
    rate_per_cwt: Decimal


def _validate(shipment: LinehaulShipment) -> None:
    if shipment.billed_weight_lb <= 0:
        raise ValueError("billed_weight_lb must be positive")
    if shipment.freight_class not in _RATE_TABLE:
        raise ValueError(f"unsupported freight_class {shipment.freight_class}")
    if shipment.discount_percent < 0 or shipment.discount_percent > Decimal("100"):
        raise ValueError("discount_percent must be between 0 and 100")
    if shipment.minimum_charge < 0:
        raise ValueError("minimum_charge cannot be negative")


def _weight_rate(shipment: LinehaulShipment, weight_lb: int) -> WeightRate:
    rates = _RATE_TABLE[shipment.freight_class]
    if weight_lb < 500:
        return WeightRate(_BREAKS[0], rates[0])
    if weight_lb < 1000:
        return WeightRate(_BREAKS[1], rates[1])
    if weight_lb < 2000:
        return WeightRate(_BREAKS[2], rates[2])
    if weight_lb < 5000:
        return WeightRate(_BREAKS[3], rates[3])
    return WeightRate(_BREAKS[4], rates[4])


def _adjusted_rate(shipment: LinehaulShipment, base_rate: Decimal, weight_lb: int) -> Decimal:
    discount_factor = Decimal("1") - (shipment.discount_percent / Decimal("100"))
    rate = base_rate * max(discount_factor, Decimal("0"))
    if shipment.origin_state in {"AK", "HI"} or shipment.destination_state in {"AK", "HI"}:
        rate *= Decimal("1") + REMOTE_UPLIFT
    if shipment.freight_class >= 125 and weight_lb < 2000:
        rate *= Decimal("1") + FRAGILE_UPLIFT
    return rate


def _charge_for_weight(shipment: LinehaulShipment, weight_lb: int) -> Decimal:
    bracket = _weight_rate(shipment, weight_lb)
    rate = _adjusted_rate(shipment, bracket.rate_per_cwt, weight_lb)
    cwt = Decimal(weight_lb) / HUNDRED
    return (rate * cwt).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_linehaul_rate_per_hundredweight(
    shipment: LinehaulShipment,
) -> Decimal:
    """Return the effective billed linehaul rate per CWT rounded to the cent.

    The returned rate reflects discount, uplifts, any beneficial deficit rating, and
    shipment minimum charge, all spread across the actual billed weight.
    """
    _validate(shipment)
    actual_charge = _charge_for_weight(shipment, shipment.billed_weight_lb)

    chosen_charge = actual_charge
    bracket = _weight_rate(shipment, shipment.billed_weight_lb)
    next_index = _BREAKS.index(bracket.minimum_weight_lb) + 1
    if next_index < len(_BREAKS):
        next_break = _BREAKS[next_index]
        shortage = next_break - shipment.billed_weight_lb
        if 0 < shortage <= DEFICIT_WINDOW_LB:
            deficit_charge = _charge_for_weight(shipment, next_break)
            if deficit_charge < chosen_charge:
                chosen_charge = deficit_charge

    if chosen_charge < shipment.minimum_charge:
        chosen_charge = shipment.minimum_charge

    actual_cwt = Decimal(shipment.billed_weight_lb) / HUNDRED
    return (chosen_charge / actual_cwt).quantize(CENT, rounding=ROUND_HALF_UP)
