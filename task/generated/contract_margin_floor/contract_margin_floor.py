"""Contract margin floor for spot and contracted truckload quotes.

The pricing service uses this floor to avoid quoting a customer sell rate that
cannot meet branch margin expectations after known variable costs. The floor is a
minimum all-in linehaul sell amount before tax.

Business rules:
- Start from carrier linehaul cost plus expected fuel and expected accessorials.
- Margin target is a percent of sell, so the minimum sell before adjustments is
  total variable cost divided by ``1 - target_margin``.
- Margin targets depend on distance bands and whether the move is contract or spot.
- Reefer freight adds 2 margin points. Hazmat adds 1 point. Combined surcharges are
  capped at 4 points.
- Dense urban deliveries below 250 miles add a flat $125 handling floor.
- Cross-border freight adds a flat $250 handling floor.
- If carrier fuel is not itemized, add a 7% fuel-risk buffer on carrier linehaul.
- Very small quotes are uplifted to a $350 absolute minimum sell.
- Same-day quotes under 200 miles require at least a 12% margin even if the normal
  target is lower.
- Margin targets are capped at 35% so the formula remains commercially reasonable.
- Final amounts round half up to the nearest cent.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ABSOLUTE_MINIMUM = Decimal("350.00")
URBAN_SHORT_HAUL_FLOOR = Decimal("125.00")
CROSS_BORDER_FLOOR = Decimal("250.00")
FUEL_RISK_RATE = Decimal("0.07")
SAMEDAY_MIN_MARGIN = Decimal("0.12")
MAX_MARGIN = Decimal("0.35")


@dataclass(frozen=True)
class MarginInputs:
    carrier_linehaul: Decimal
    expected_fuel: Decimal = Decimal("0.00")
    expected_accessorials: Decimal = Decimal("0.00")
    miles: int = 0
    is_contract: bool = False
    is_reefer: bool = False
    is_hazmat: bool = False
    is_urban_delivery: bool = False
    is_cross_border: bool = False
    same_day: bool = False
    fuel_included_in_cost: bool = True


def _validate(inputs: MarginInputs) -> None:
    if inputs.carrier_linehaul < 0:
        raise ValueError("carrier_linehaul cannot be negative")
    if inputs.expected_fuel < 0:
        raise ValueError("expected_fuel cannot be negative")
    if inputs.expected_accessorials < 0:
        raise ValueError("expected_accessorials cannot be negative")
    if inputs.miles < 0:
        raise ValueError("miles cannot be negative")


def _base_margin(miles: int, is_contract: bool) -> Decimal:
    if is_contract:
        if miles <= 250:
            return Decimal("0.10")
        if miles <= 700:
            return Decimal("0.08")
        return Decimal("0.07")
    if miles <= 250:
        return Decimal("0.14")
    if miles <= 700:
        return Decimal("0.12")
    return Decimal("0.10")


def _target_margin(inputs: MarginInputs) -> Decimal:
    margin = _base_margin(inputs.miles, inputs.is_contract)
    surcharge = Decimal("0.00")
    if inputs.is_reefer:
        surcharge += Decimal("0.02")
    if inputs.is_hazmat:
        surcharge += Decimal("0.01")
    if surcharge > Decimal("0.04"):
        surcharge = Decimal("0.04")
    margin += surcharge
    if inputs.same_day and inputs.miles < 200 and margin < SAMEDAY_MIN_MARGIN:
        margin = SAMEDAY_MIN_MARGIN
    if margin > MAX_MARGIN:
        margin = MAX_MARGIN
    return margin


def _total_variable_cost(inputs: MarginInputs) -> Decimal:
    total = inputs.carrier_linehaul + inputs.expected_fuel + inputs.expected_accessorials
    if not inputs.fuel_included_in_cost:
        total += (inputs.carrier_linehaul * FUEL_RISK_RATE).quantize(CENT, rounding=ROUND_HALF_UP)
    return total


def _flat_floors(inputs: MarginInputs) -> Decimal:
    floor = Decimal("0.00")
    if inputs.is_urban_delivery and inputs.miles < 250:
        floor += URBAN_SHORT_HAUL_FLOOR
    if inputs.is_cross_border:
        floor += CROSS_BORDER_FLOOR
    return floor


def calculate_contract_margin_floor(inputs: MarginInputs) -> Decimal:
    """Minimum sell rate required to satisfy margin and handling rules.

    The result is an all-in customer sell amount in dollars.
    """
    _validate(inputs)
    total_cost = _total_variable_cost(inputs)
    margin = _target_margin(inputs)
    base_sell = total_cost / (Decimal("1.00") - margin)
    amount = base_sell + _flat_floors(inputs)
    if amount < ABSOLUTE_MINIMUM:
        amount = ABSOLUTE_MINIMUM
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)
