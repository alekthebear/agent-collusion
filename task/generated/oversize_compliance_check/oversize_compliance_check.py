"""Oversize compliance screening for one truckload movement.

This module applies simplified legal size and weight checks before rating or booking.
Business rules reflect common planning defaults used by operations:
- Base legal limits are 8 ft 6 in wide, 13 ft 6 in high, 53 ft long, and 80,000 lb gross.
- Some jurisdictions differ: TX allows 14 ft height, FL allows 48 ft length on this lane,
  and NV allows 129,000 lb gross on divisible overweight permits.
- Width over 8 ft 6 in requires an oversize permit. Width over 12 ft requires one escort,
  and over 14 ft requires two escorts.
- Height over the jurisdiction limit requires a route survey. Height over the limit by more
  than 12 in is rejected because our standard program will not route it automatically.
- Length over the jurisdiction limit requires a permit. Length over 80 ft also needs one escort.
- Weight over the jurisdiction limit requires an overweight permit when the load is divisible.
  Non-divisible loads over the limit are rejected by this check. If gross weight exceeds the
  jurisdiction limit by more than 20,000 lb, two escorts are also required.
- Mobile cranes are handled specially: up to 14 ft 6 in wide may move with permits and escorts,
  but above that width they are rejected here.
- Any movement marked hazmat is rejected when width exceeds 12 ft or weight exceeds 110,000 lb.
"""

from dataclasses import dataclass
from decimal import Decimal

BASE_WIDTH_IN = 102
BASE_HEIGHT_IN = 162
BASE_LENGTH_FT = 53
BASE_WEIGHT_LB = 80000


@dataclass(frozen=True)
class LoadProfile:
    width_in: int
    height_in: int
    length_ft: Decimal
    gross_weight_lb: int
    jurisdiction: str
    divisible_load: bool = True
    hazmat: bool = False
    mobile_crane: bool = False


@dataclass(frozen=True)
class ComplianceResult:
    compliant: bool
    needs_permit: bool
    route_survey_required: bool
    escort_count: int
    reject_reason: str | None


def _limits(jurisdiction: str) -> tuple[int, int, Decimal, int]:
    code = jurisdiction.upper()
    height = 168 if code == "TX" else BASE_HEIGHT_IN
    length = Decimal("48") if code == "FL" else Decimal("53")
    weight = 129000 if code == "NV" else BASE_WEIGHT_LB
    return BASE_WIDTH_IN, height, length, weight


def _validate(load: LoadProfile) -> None:
    if load.width_in <= 0 or load.height_in <= 0 or load.length_ft <= 0 or load.gross_weight_lb <= 0:
        raise ValueError("dimensions and weight must be positive")
    if load.jurisdiction.strip() == "":
        raise ValueError("jurisdiction is required")


def _escort_for_width(width_in: int) -> int:
    if width_in > 168:
        return 2
    if width_in > 144:
        return 1
    return 0


def _max(a: int, b: int) -> int:
    return a if a >= b else b


def evaluate_oversize_compliance_check(load: LoadProfile) -> ComplianceResult:
    """Evaluate simplified oversize and overweight rules for one movement."""
    _validate(load)
    width_limit, height_limit, length_limit, weight_limit = _limits(load.jurisdiction)

    needs_permit = False
    route_survey_required = False
    escort_count = 0

    if load.mobile_crane and load.width_in > 174:
        return ComplianceResult(False, True, False, 2, "mobile crane exceeds program width")

    if load.width_in > width_limit:
        needs_permit = True
        escort_count = _max(escort_count, _escort_for_width(load.width_in))

    if load.height_in > height_limit:
        needs_permit = True
        route_survey_required = True
        if load.height_in - height_limit > 12:
            return ComplianceResult(False, True, True, escort_count, "height exceeds auto-routing tolerance")

    if load.length_ft > length_limit:
        needs_permit = True
        if load.length_ft > Decimal("80"):
            escort_count = _max(escort_count, 1)

    if load.gross_weight_lb > weight_limit:
        needs_permit = True
        if not load.divisible_load:
            return ComplianceResult(False, True, route_survey_required, escort_count, "non-divisible overweight load")
        if load.gross_weight_lb - weight_limit > 20000:
            escort_count = _max(escort_count, 2)

    if load.hazmat and (load.width_in > 144 or load.gross_weight_lb > 110000):
        return ComplianceResult(False, needs_permit or True, route_survey_required, escort_count, "hazmat exceeds corridor allowance")

    return ComplianceResult(True, needs_permit, route_survey_required, escort_count, None)
