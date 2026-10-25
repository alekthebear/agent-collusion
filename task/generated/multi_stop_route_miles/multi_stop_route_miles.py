"""Compute settled route miles for a multi-stop load from ordered stop data.

Business rules used by Tidewater Freight rating and settlement:
- A route is an ordered sequence of stops. There must be at least two stops.
- Each stop may provide ``leg_miles_from_previous`` for the inbound leg. The first stop
  cannot have an inbound leg.
- When a non-first stop omits leg miles, the system may derive them from coordinates if
  both that stop and the previous stop have latitude/longitude. Derived miles are a simple
  road-use proxy: great-circle miles multiplied by 1.18, then rounded to the nearest whole
  mile.
- Very short non-zero derived legs are floored to 1 mile so adjacent facilities do not
  disappear in settlement.
- Provided leg miles are accepted as decimals but quantized to whole miles using half-up
  rounding. Negative leg miles are invalid.
- Optional out-of-route penalties are added after all legs. The first 15 extra miles are
  ignored as normal terminal and truck-stop variance. Remaining penalty miles are rounded
  up to the next whole mile.
- If a route has more than 4 stops, 2 handling miles are added for each stop after the
  fourth. This reflects common yard circulation on dense multi-stop routes.
- The returned route total is a whole-mile ``Decimal``.
"""

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from math import asin, cos, radians, sin, sqrt

WHOLE_MILE = Decimal("1")
EARTH_RADIUS_MILES = 3958.761
ROAD_FACTOR = Decimal("1.18")
OUT_OF_ROUTE_FREE = Decimal("15")
DENSE_STOP_SURCHARGE_PER_STOP = Decimal("2")


@dataclass(frozen=True)
class RouteStop:
    sequence: int
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    leg_miles_from_previous: Decimal | None = None


@dataclass(frozen=True)
class RoutePlan:
    stops: tuple[RouteStop, ...]
    out_of_route_miles: Decimal = Decimal("0")


def _validate(plan: RoutePlan) -> None:
    if len(plan.stops) < 2:
        raise ValueError("route must contain at least two stops")
    expected = 1
    for stop in plan.stops:
        if stop.sequence != expected:
            raise ValueError("stops must be numbered consecutively starting at 1")
        if stop.sequence == 1 and stop.leg_miles_from_previous is not None:
            raise ValueError("first stop cannot have inbound leg miles")
        if stop.leg_miles_from_previous is not None and stop.leg_miles_from_previous < 0:
            raise ValueError("leg miles cannot be negative")
        if stop.latitude is not None and not (Decimal("-90") <= stop.latitude <= Decimal("90")):
            raise ValueError("latitude out of range")
        if stop.longitude is not None and not (Decimal("-180") <= stop.longitude <= Decimal("180")):
            raise ValueError("longitude out of range")
        expected += 1
    if plan.out_of_route_miles < 0:
        raise ValueError("out_of_route_miles cannot be negative")


def _quantize_leg(miles: Decimal) -> Decimal:
    return miles.quantize(WHOLE_MILE, rounding=ROUND_HALF_UP)


def _derived_leg_miles(previous: RouteStop, current: RouteStop) -> Decimal:
    if None in (previous.latitude, previous.longitude, current.latitude, current.longitude):
        raise ValueError("missing leg miles and insufficient coordinates to derive miles")
    lat1 = radians(float(previous.latitude))
    lon1 = radians(float(previous.longitude))
    lat2 = radians(float(current.latitude))
    lon2 = radians(float(current.longitude))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    great_circle = 2 * EARTH_RADIUS_MILES * asin(sqrt(a))
    road = Decimal(str(great_circle)) * ROAD_FACTOR
    rounded = _quantize_leg(road)
    if road > 0 and rounded == 0:
        return Decimal("1")
    return rounded


def _leg_miles(previous: RouteStop, current: RouteStop) -> Decimal:
    if current.leg_miles_from_previous is not None:
        return _quantize_leg(current.leg_miles_from_previous)
    return _derived_leg_miles(previous, current)


def _out_of_route_penalty(extra_miles: Decimal) -> Decimal:
    if extra_miles <= OUT_OF_ROUTE_FREE:
        return Decimal("0")
    billable = extra_miles - OUT_OF_ROUTE_FREE
    return billable.quantize(WHOLE_MILE, rounding=ROUND_CEILING)


def calculate_multi_stop_route_miles(plan: RoutePlan) -> Decimal:
    """Return settled route miles as a whole-mile Decimal.

    Legs use provided miles when present; otherwise they are derived from coordinates.
    Out-of-route miles add a post-route penalty after a 15-mile free allowance.
    Dense routes with more than 4 stops receive 2 extra miles per stop beyond the fourth.
    """
    _validate(plan)
    total = Decimal("0")
    for previous, current in zip(plan.stops, plan.stops[1:]):
        total += _leg_miles(previous, current)
    total += _out_of_route_penalty(plan.out_of_route_miles)
    if len(plan.stops) > 4:
        total += DENSE_STOP_SURCHARGE_PER_STOP * (len(plan.stops) - 4)
    return total.quantize(WHOLE_MILE, rounding=ROUND_HALF_UP)
