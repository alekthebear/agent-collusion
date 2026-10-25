"""Plan fuel stop spacing for over-the-road moves.

Dispatch uses this planner before tendering a trip to estimate how many en-route
fuel stops a driver should need and how far apart they should be. The rules are
conservative because routes vary, pumps are not always available at the exact mile,
and drivers should not plan to burn into protected reserve.

Business rules:
- ``usable_gallons`` must be positive, ``reserve_gallons`` cannot be negative, and
  reserve must be less than usable fuel.
- Effective planning range uses only ``usable_gallons - reserve_gallons`` and is
  multiplied by a route factor. Standard routes plan at 97% of modeled range;
  mountain routes at 92%.
- If reefer fuel support is needed, an additional 5% range reduction applies.
- Planned leg range is rounded down to the nearest 25 miles and never allowed below
  100 miles when the truck has any positive effective range.
- Trips at or under 150 miles require no fuel stop even if the rounded leg range is
  smaller; local moves can start full and finish inside reserve policy.
- Otherwise, the minimum stop count is the smallest integer where each leg fits the
  planned leg range. Legs are route miles divided evenly across stops plus origin
  and destination.
- To avoid nuisance stops, if the computed average leg would be under 180 miles and
  at least one stop is planned, reduce the stop count by one when the longer average
  leg is still within 110% of planned leg range.
- Returned leg miles are rounded to the nearest whole mile using half-up rounding.
"""

from dataclasses import dataclass
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
MILE_BLOCK = Decimal("25")
MIN_LEG_MILES = Decimal("100")
SHORT_HAUL_EXEMPT_MILES = Decimal("150")
NUISANCE_LEG_THRESHOLD = Decimal("180")
NUISANCE_TOLERANCE = Decimal("1.10")
STANDARD_ROUTE_FACTOR = Decimal("0.97")
MOUNTAIN_ROUTE_FACTOR = Decimal("0.92")
REEFER_FACTOR = Decimal("0.95")


@dataclass(frozen=True)
class FuelPlanInput:
    route_miles: Decimal
    usable_gallons: Decimal
    reserve_gallons: Decimal
    mpg: Decimal
    mountain_route: bool = False
    reefer_support: bool = False


@dataclass(frozen=True)
class FuelStopPlan:
    planned_stop_count: int
    average_leg_miles: int
    planned_leg_range_miles: int
    effective_range_miles: Decimal


def _validate(data: FuelPlanInput) -> None:
    if data.route_miles < 0:
        raise ValueError("route_miles cannot be negative")
    if data.usable_gallons <= 0:
        raise ValueError("usable_gallons must be positive")
    if data.reserve_gallons < 0:
        raise ValueError("reserve_gallons cannot be negative")
    if data.reserve_gallons >= data.usable_gallons:
        raise ValueError("reserve_gallons must be less than usable_gallons")
    if data.mpg <= 0:
        raise ValueError("mpg must be positive")


def _effective_range(data: FuelPlanInput) -> Decimal:
    gallons = data.usable_gallons - data.reserve_gallons
    route_factor = MOUNTAIN_ROUTE_FACTOR if data.mountain_route else STANDARD_ROUTE_FACTOR
    miles = gallons * data.mpg * route_factor
    if data.reefer_support:
        miles *= REEFER_FACTOR
    return miles.quantize(CENT, rounding=ROUND_HALF_UP)


def _planned_leg_range(effective_range: Decimal) -> Decimal:
    if effective_range <= 0:
        return Decimal("0")
    blocks = (effective_range / MILE_BLOCK).to_integral_value(rounding=ROUND_FLOOR)
    rounded = blocks * MILE_BLOCK
    if rounded < MIN_LEG_MILES:
        return MIN_LEG_MILES
    return rounded


def _minimum_stop_count(route_miles: Decimal, leg_range: Decimal) -> int:
    if route_miles <= SHORT_HAUL_EXEMPT_MILES:
        return 0
    whole, remainder = divmod(route_miles, leg_range)
    legs_needed = int(whole) + (1 if remainder else 0)
    return max(0, legs_needed - 1)


def _average_leg(route_miles: Decimal, stop_count: int) -> Decimal:
    return route_miles / Decimal(stop_count + 1)


def calculate_fuel_stop_plan(data: FuelPlanInput) -> FuelStopPlan:
    """Return stop count and target spacing for a route.

    The planner protects reserve fuel, applies route-condition discounts, rounds the
    usable leg range down to operational 25-mile blocks, then chooses the smallest
    stop count that fits the trip. A nuisance-stop reduction may remove one stop.
    """
    _validate(data)
    effective_range = _effective_range(data)
    leg_range = _planned_leg_range(effective_range)

    if data.route_miles == 0:
        return FuelStopPlan(0, 0, int(leg_range), effective_range)

    stop_count = _minimum_stop_count(data.route_miles, leg_range)
    average_leg = _average_leg(data.route_miles, stop_count)

    if stop_count > 0 and average_leg < NUISANCE_LEG_THRESHOLD:
        fewer_stop_average = _average_leg(data.route_miles, stop_count - 1)
        if fewer_stop_average <= leg_range * NUISANCE_TOLERANCE:
            stop_count -= 1
            average_leg = fewer_stop_average

    average_leg_miles = int(average_leg.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return FuelStopPlan(
        planned_stop_count=stop_count,
        average_leg_miles=average_leg_miles,
        planned_leg_range_miles=int(leg_range),
        effective_range_miles=effective_range,
    )
