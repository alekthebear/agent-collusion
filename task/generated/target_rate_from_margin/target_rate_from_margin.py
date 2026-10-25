"""Target customer all-in rate needed to hit a gross margin goal.

Tidewater pricing works backward from projected buy cost and surcharge mix. Gross
margin percent is measured on customer revenue: ``(revenue - cost) / revenue``.
Fuel and other pass-through surcharges are billed through to the customer and do
not carry additional margin in this helper, so they are added after the base
linehaul target is set.

Business rules:
- ``projected_cost`` is the carrier buy cost before customer surcharges.
- ``fuel_surcharge`` and ``other_surcharges`` are customer pass-through amounts.
- Margin targets are allowed from 0% through 49.5%; higher targets are rejected.
- The baseline linehaul target is ``cost / (1 - margin)``.
- Standard freight has a minimum gross profit floor: $85 when cost is under $400,
  otherwise $125.
- Refrigerated freight adds a $50 premium; hazmat adds $75. These premiums stack.
- Partial shipments are priced from the pure margin result plus premiums, then
  discounted 7%, but never below cost plus surcharges plus $40 gross profit.
  The standard freight profit floors do not apply to partials.
- Final all-in customer rates cannot be below $125 and are rounded to the nearest
  whole dollar, represented with cents.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
DOLLAR = Decimal("1")
ALL_IN_FLOOR = Decimal("125")
LOW_COST_PROFIT_FLOOR = Decimal("85")
STANDARD_PROFIT_FLOOR = Decimal("125")
PARTIAL_MIN_PROFIT = Decimal("40")
REEFER_PREMIUM = Decimal("50")
HAZMAT_PREMIUM = Decimal("75")
PARTIAL_DISCOUNT = Decimal("0.93")
MAX_MARGIN = Decimal("0.495")


@dataclass(frozen=True)
class ShipmentProfile:
    projected_cost: Decimal
    fuel_surcharge: Decimal = Decimal("0.00")
    other_surcharges: Decimal = Decimal("0.00")
    is_partial: bool = False
    is_reefer: bool = False
    is_hazmat: bool = False


@dataclass(frozen=True)
class MarginTarget:
    gross_margin_percent: Decimal


def _validate(shipment: ShipmentProfile, target: MarginTarget) -> None:
    for name, value in (
        ("projected_cost", shipment.projected_cost),
        ("fuel_surcharge", shipment.fuel_surcharge),
        ("other_surcharges", shipment.other_surcharges),
    ):
        if value < 0:
            raise ValueError(f"{name} must be non-negative")
    if shipment.projected_cost <= 0:
        raise ValueError("projected_cost must be greater than zero")
    if target.gross_margin_percent < 0 or target.gross_margin_percent > MAX_MARGIN:
        raise ValueError("gross_margin_percent must be between 0 and 0.495")


def _profit_floor(cost: Decimal) -> Decimal:
    return LOW_COST_PROFIT_FLOOR if cost < Decimal("400") else STANDARD_PROFIT_FLOOR


def _margin_based_linehaul(cost: Decimal, margin: Decimal) -> Decimal:
    return cost / (Decimal("1.00") - margin)


def _special_premiums(shipment: ShipmentProfile) -> Decimal:
    premium = Decimal("0")
    if shipment.is_reefer:
        premium += REEFER_PREMIUM
    if shipment.is_hazmat:
        premium += HAZMAT_PREMIUM
    return premium


def _round_customer_rate(amount: Decimal) -> Decimal:
    return amount.quantize(DOLLAR, rounding=ROUND_HALF_UP).quantize(CENT)


def calculate_target_rate_from_margin(
    shipment: ShipmentProfile,
    target: MarginTarget,
) -> Decimal:
    """Return the all-in customer rate needed to meet pricing rules."""
    _validate(shipment, target)

    base_linehaul = _margin_based_linehaul(
        shipment.projected_cost, target.gross_margin_percent
    ) + _special_premiums(shipment)

    if shipment.is_partial:
        total = (
            base_linehaul + shipment.fuel_surcharge + shipment.other_surcharges
        ) * PARTIAL_DISCOUNT
        min_partial_total = (
            shipment.projected_cost
            + shipment.fuel_surcharge
            + shipment.other_surcharges
            + PARTIAL_MIN_PROFIT
        )
        if total < min_partial_total:
            total = min_partial_total
    else:
        min_linehaul = shipment.projected_cost + _profit_floor(shipment.projected_cost)
        linehaul = base_linehaul if base_linehaul > min_linehaul else min_linehaul
        total = linehaul + shipment.fuel_surcharge + shipment.other_surcharges

    if total < ALL_IN_FLOOR:
        total = ALL_IN_FLOOR
    return _round_customer_rate(total)
