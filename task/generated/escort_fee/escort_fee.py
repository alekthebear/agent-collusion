"""Escort and pilot-car charges for oversize loads across route segments.

Tidewater bills escort service from trip plans that list each route segment and the
jurisdiction's escort requirement. A segment may require no escort, one escort, or
two escorts. Billing is usually pass-through at the vendor's escort rate, but some
accounts are billed at a markup instead. Charges are computed per loaded trip and
then multiplied by the number of trips.

Business rules:
- Segment distance is billed in whole miles rounded up from any fractional mile.
- Segments under 10 billed miles are charged the 10-mile minimum when an escort is
  required.
- One escort uses the base escort rate; two escorts use double the segment charge.
- A night segment adds a flat surcharge per escort on that segment.
- A metro segment adds a flat surcharge once per segment when any escort is required.
- Segments in CA or NY have a jurisdiction permit admin fee once per segment when an
  escort is required.
- Billable mode is either pass-through (vendor cost) or markup on vendor cost.
- Markup percent is applied to the per-trip subtotal and rounded half up to cents.
- Multi-trip plans of 3 or more trips receive a 5% discount on the final billed total.
- The final amount is rounded half up to cents and never negative.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
MIN_BILLED_MILES = 10
NIGHT_SURCHARGE = Decimal("35.00")
METRO_SURCHARGE = Decimal("25.00")
SPECIAL_ADMIN_FEE = Decimal("18.50")
MULTI_TRIP_DISCOUNT = Decimal("0.05")
SPECIAL_JURISDICTIONS = {"CA", "NY"}


@dataclass(frozen=True)
class RouteSegment:
    miles: Decimal
    escorts_required: int
    jurisdiction: str
    night_move: bool = False
    metro_area: bool = False


@dataclass(frozen=True)
class EscortContract:
    base_rate_per_mile: Decimal = Decimal("2.40")
    billing_mode: str = "pass_through"
    markup_percent: Decimal = Decimal("0.00")


@dataclass(frozen=True)
class EscortPlan:
    segments: tuple[RouteSegment, ...]
    trips: int = 1


def _validate_segment(segment: RouteSegment) -> None:
    if segment.miles < 0:
        raise ValueError("segment miles cannot be negative")
    if segment.escorts_required not in (0, 1, 2):
        raise ValueError("escorts_required must be 0, 1, or 2")
    if not segment.jurisdiction or segment.jurisdiction.strip() != segment.jurisdiction:
        raise ValueError("jurisdiction must be a non-empty trimmed code")


def _validate_contract(contract: EscortContract) -> None:
    if contract.base_rate_per_mile < 0:
        raise ValueError("base_rate_per_mile cannot be negative")
    if contract.billing_mode not in {"pass_through", "markup"}:
        raise ValueError("billing_mode must be pass_through or markup")
    if contract.markup_percent < 0:
        raise ValueError("markup_percent cannot be negative")
    if contract.billing_mode == "pass_through" and contract.markup_percent != Decimal("0.00"):
        raise ValueError("pass_through billing cannot include markup_percent")


def _billed_miles(miles: Decimal) -> int:
    whole = int(miles)
    return whole if miles == Decimal(whole) else whole + 1


def _segment_vendor_cost(segment: RouteSegment, rate: Decimal) -> Decimal:
    if segment.escorts_required == 0:
        return Decimal("0.00")
    billed_miles = max(_billed_miles(segment.miles), MIN_BILLED_MILES)
    amount = rate * billed_miles * segment.escorts_required
    if segment.night_move:
        amount += NIGHT_SURCHARGE * segment.escorts_required
    if segment.metro_area:
        amount += METRO_SURCHARGE
    if segment.jurisdiction in SPECIAL_JURISDICTIONS:
        amount += SPECIAL_ADMIN_FEE
    return amount


def _apply_billing(subtotal: Decimal, contract: EscortContract) -> Decimal:
    if contract.billing_mode == "pass_through":
        return subtotal
    factor = Decimal("1.00") + (contract.markup_percent / Decimal("100"))
    return (subtotal * factor).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_escort_fee(plan: EscortPlan, contract: EscortContract = EscortContract()) -> Decimal:
    """Return the billed escort fee for the whole load plan.

    The function totals vendor cost across all route segments for one trip, applies the
    contract billing rule, multiplies by trip count, then applies any multi-trip
    discount. The result is rounded to cents.
    """
    if plan.trips < 1:
        raise ValueError("trips must be at least 1")
    _validate_contract(contract)
    per_trip = Decimal("0.00")
    for segment in plan.segments:
        _validate_segment(segment)
        per_trip += _segment_vendor_cost(segment, contract.base_rate_per_mile)
    billed = _apply_billing(per_trip, contract) * plan.trips
    if plan.trips >= 3:
        billed *= Decimal("1.00") - MULTI_TRIP_DISCOUNT
    if billed < 0:
        return Decimal("0.00")
    return billed.quantize(CENT, rounding=ROUND_HALF_UP)
