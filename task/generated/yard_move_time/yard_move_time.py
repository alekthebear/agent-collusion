"""Expected yard move duration for repositioning a trailer inside a facility.

Yard moves cover the elapsed working time from when a hostler is dispatched until the
trailer is set in the destination door or parking row. Planning uses the standard
rules below so dispatch can compare moves consistently across sites.

Base minutes depend on facility size. Added travel time comes from spot distance,
measured in driven tenths of a mile, with partial tenths rounded up because even a
short extra pull still requires a full lane segment. Congestion increases only the
travel-and-hook portion, not paperwork. Empty or pre-staged trailers are faster to
pick up than loaded trailers not yet ready. A destination in the same row gets a
small credit, but the move can never plan below the operational minimum.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
MINIMUM_MINUTES = Decimal("6.00")


@dataclass(frozen=True)
class YardMoveRequest:
    """Inputs used to estimate one yard move in minutes."""

    facility_acres: int
    spot_distance_miles: Decimal
    congestion_factor: Decimal = Decimal("1.00")
    trailer_ready: bool = True
    loaded: bool = True
    same_row: bool = False


@dataclass(frozen=True)
class YardMovePolicy:
    """Operational planning assumptions shared across facilities."""

    small_facility_max_acres: int = 80
    medium_facility_max_acres: int = 200
    small_base_minutes: Decimal = Decimal("7.00")
    medium_base_minutes: Decimal = Decimal("10.00")
    large_base_minutes: Decimal = Decimal("14.00")
    minutes_per_tenth_mile: Decimal = Decimal("1.20")
    ready_credit_minutes: Decimal = Decimal("1.00")
    not_ready_loaded_penalty_minutes: Decimal = Decimal("4.00")
    not_ready_empty_penalty_minutes: Decimal = Decimal("2.00")
    same_row_credit_minutes: Decimal = Decimal("1.50")


def _validate(request: YardMoveRequest) -> None:
    if request.facility_acres <= 0:
        raise ValueError("facility_acres must be positive")
    if request.spot_distance_miles < 0:
        raise ValueError("spot_distance_miles cannot be negative")
    if request.congestion_factor < Decimal("0.80") or request.congestion_factor > Decimal("1.60"):
        raise ValueError("congestion_factor must be between 0.80 and 1.60")


def _base_minutes(acres: int, policy: YardMovePolicy) -> Decimal:
    if acres <= policy.small_facility_max_acres:
        return policy.small_base_minutes
    if acres <= policy.medium_facility_max_acres:
        return policy.medium_base_minutes
    return policy.large_base_minutes


def _distance_tenths(distance_miles: Decimal) -> int:
    """Started tenths of a mile, rounded up."""
    tenths = distance_miles * Decimal("10")
    whole = int(tenths)
    return whole if tenths == Decimal(whole) else whole + 1


def _readiness_adjustment(request: YardMoveRequest, policy: YardMovePolicy) -> Decimal:
    if request.trailer_ready:
        return -policy.ready_credit_minutes
    if request.loaded:
        return policy.not_ready_loaded_penalty_minutes
    return policy.not_ready_empty_penalty_minutes


def calculate_yard_move_time(
    request: YardMoveRequest, policy: YardMovePolicy = YardMovePolicy()
) -> Decimal:
    """Expected yard move duration in minutes, rounded to the nearest hundredth.

    The estimate adds a facility-size base and a distance component. Congestion applies
    only to the distance component plus readiness adjustment. Same-row drops reduce the
    final estimate. The result is floored at six minutes.
    """
    _validate(request)
    base = _base_minutes(request.facility_acres, policy)
    tenths = _distance_tenths(request.spot_distance_miles)
    travel = Decimal(tenths) * policy.minutes_per_tenth_mile
    variable = travel + _readiness_adjustment(request, policy)
    congested_variable = variable * request.congestion_factor
    total = base + congested_variable
    if request.same_row:
        total -= policy.same_row_credit_minutes
    if total < MINIMUM_MINUTES:
        total = MINIMUM_MINUTES
    return total.quantize(CENT, rounding=ROUND_HALF_UP)
