"""Permit charges for oversize and overweight moves.

Tidewater bills permit procurement from state-level schedules plus a customer-facing
service markup. This module handles one move summarized at the order level rather
than per-state detail. The business rules reflect the common policies our permit desk
uses:

* Base permit fee depends on the governing trigger for the move. If both dimensions
  and weight require permits, the higher of the two state schedule amounts is used,
  not both.
* Size trigger: loads wider than 8'6" or taller than 13'6" require oversize permits.
  Width up to 12' and height up to 14'6" uses the standard oversize fee; anything
  above either threshold uses the superload oversize fee.
* Weight trigger: gross weight up to 80,000 lb is non-permitted. From 80,001 to
  120,000 lb uses the standard overweight fee; above 120,000 lb uses the heavy
  overweight fee.
* The state fee is multiplied by the number of jurisdictions, with one exception:
  contiguous local runs wholly within one state and under 10 route miles do not bill
  a permit even if dimensions or weight would otherwise require one.
* A same-day rush request adds a flat rush surcharge per jurisdiction.
* Customer markup is then applied to the subtotal. Markup rounds half up to the cent,
  but preferred customers have a minimum markup of $15.00 on any permitted move.
* Final billed amount is rounded to cents and never negative.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
STANDARD_OVERSIZE_FEE = Decimal("25.00")
SUPERLOAD_OVERSIZE_FEE = Decimal("60.00")
STANDARD_OVERWEIGHT_FEE = Decimal("40.00")
HEAVY_OVERWEIGHT_FEE = Decimal("90.00")
RUSH_SURCHARGE = Decimal("20.00")
MIN_MARKUP = Decimal("15.00")

WIDTH_LIMIT_FT = Decimal("8.5")
HEIGHT_LIMIT_FT = Decimal("13.5")
SUPERLOAD_WIDTH_FT = Decimal("12.0")
SUPERLOAD_HEIGHT_FT = Decimal("14.5")
STANDARD_WEIGHT_LIMIT = 80000
HEAVY_WEIGHT_LIMIT = 120000


@dataclass(frozen=True)
class PermitRequest:
    jurisdictions: int
    route_miles: Decimal
    width_ft: Decimal
    height_ft: Decimal
    gross_weight_lb: int
    rush: bool = False
    preferred_customer: bool = False


@dataclass(frozen=True)
class BillingPolicy:
    markup_rate: Decimal = Decimal("0.18")
    rush_surcharge: Decimal = RUSH_SURCHARGE
    minimum_markup: Decimal = MIN_MARKUP


def _validate(request: PermitRequest, policy: BillingPolicy) -> None:
    if request.jurisdictions < 1:
        raise ValueError("jurisdictions must be at least 1")
    if request.route_miles < 0:
        raise ValueError("route_miles cannot be negative")
    if request.width_ft <= 0 or request.height_ft <= 0:
        raise ValueError("dimensions must be positive")
    if request.gross_weight_lb <= 0:
        raise ValueError("gross_weight_lb must be positive")
    if policy.markup_rate < 0:
        raise ValueError("markup_rate cannot be negative")
    if policy.rush_surcharge < 0 or policy.minimum_markup < 0:
        raise ValueError("policy charges cannot be negative")


def _oversize_fee(width_ft: Decimal, height_ft: Decimal) -> Decimal:
    if width_ft <= WIDTH_LIMIT_FT and height_ft <= HEIGHT_LIMIT_FT:
        return Decimal("0.00")
    if width_ft > SUPERLOAD_WIDTH_FT or height_ft > SUPERLOAD_HEIGHT_FT:
        return SUPERLOAD_OVERSIZE_FEE
    return STANDARD_OVERSIZE_FEE


def _overweight_fee(gross_weight_lb: int) -> Decimal:
    if gross_weight_lb <= STANDARD_WEIGHT_LIMIT:
        return Decimal("0.00")
    if gross_weight_lb <= HEAVY_WEIGHT_LIMIT:
        return STANDARD_OVERWEIGHT_FEE
    return HEAVY_OVERWEIGHT_FEE


def _is_local_exempt(request: PermitRequest) -> bool:
    return request.jurisdictions == 1 and request.route_miles < Decimal("10.00")


def _markup(subtotal: Decimal, preferred_customer: bool, policy: BillingPolicy) -> Decimal:
    if subtotal == Decimal("0.00"):
        return Decimal("0.00")
    amount = (subtotal * policy.markup_rate).quantize(CENT, rounding=ROUND_HALF_UP)
    if preferred_customer and amount < policy.minimum_markup:
        return policy.minimum_markup
    return amount


def calculate_permits_fee(
    request: PermitRequest, policy: BillingPolicy = BillingPolicy()
) -> Decimal:
    """Total billed permit charge for a move, rounded to cents.

    The governing state fee is the higher of oversize and overweight schedules, then
    multiplied by jurisdictions. Rush surcharges and markup are added after that.
    """
    _validate(request, policy)
    if _is_local_exempt(request):
        return Decimal("0.00")

    state_fee = max(
        _oversize_fee(request.width_ft, request.height_ft),
        _overweight_fee(request.gross_weight_lb),
    )
    if state_fee == Decimal("0.00"):
        return Decimal("0.00")

    subtotal = state_fee * request.jurisdictions
    if request.rush:
        subtotal += policy.rush_surcharge * request.jurisdictions

    total = subtotal + _markup(subtotal, request.preferred_customer, policy)
    if total < 0:
        return Decimal("0.00")
    return total.quantize(CENT, rounding=ROUND_HALF_UP)
