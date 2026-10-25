"""Temperature compliance checks for refrigerated shipments.

Food and pharmaceutical tenders often specify a target trailer setpoint, an
allowed product temperature band, and extra restrictions for long transit. This
module evaluates whether a planned setpoint range and trip duration comply with
those tender rules.

Business rules:
- Compliance is evaluated against the full planned setpoint range, not just the
  midpoint; both the minimum and maximum planned setpoint must be acceptable.
- A setpoint may run inside the product's allowed band, plus a symmetric control
  tolerance in degrees Fahrenheit. This reflects normal reefer cycling.
- Control tolerance defaults to 1.5 F and is rounded to the nearest tenth using
  half-up before comparisons.
- If the shipment is marked temperature-sensitive, tolerance is tightened by
  0.5 F, but never below 0.5 F total.
- Long transit tightens the upper end because warm drift is riskier: trips over
  24 hours reduce the effective warm limit by 0.5 F, and trips over 48 hours
  reduce it by 1.0 F total.
- Frozen freight may not plan a setpoint above 10.0 F even if the general band
  plus tolerance would allow it.
- If the planned setpoint range is a single point exactly on a computed boundary,
  it is compliant; boundaries are inclusive.
- Results include the rounded effective limits and a reason code for audit use.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

TENTH = Decimal("0.1")
ZERO = Decimal("0.0")
DEFAULT_TOLERANCE = Decimal("1.5")
FROZEN_MAX_SETPOINT = Decimal("10.0")


@dataclass(frozen=True)
class PlannedSetpointRange:
    minimum_f: Decimal
    maximum_f: Decimal


@dataclass(frozen=True)
class ProductTemperatureRequirements:
    minimum_product_f: Decimal
    maximum_product_f: Decimal
    transit_hours: int
    temperature_sensitive: bool = False
    frozen: bool = False
    control_tolerance_f: Decimal = DEFAULT_TOLERANCE


@dataclass(frozen=True)
class TemperatureComplianceResult:
    compliant: bool
    effective_min_setpoint_f: Decimal
    effective_max_setpoint_f: Decimal
    reason_code: str


def _round_tenth(value: Decimal) -> Decimal:
    return value.quantize(TENTH, rounding=ROUND_HALF_UP)


def _validate(plan: PlannedSetpointRange, req: ProductTemperatureRequirements) -> None:
    if plan.minimum_f > plan.maximum_f:
        raise ValueError("planned minimum setpoint exceeds maximum setpoint")
    if req.minimum_product_f > req.maximum_product_f:
        raise ValueError("product minimum temperature exceeds maximum temperature")
    if req.transit_hours < 0:
        raise ValueError("transit hours cannot be negative")
    if req.control_tolerance_f < ZERO:
        raise ValueError("control tolerance cannot be negative")


def _effective_tolerance(req: ProductTemperatureRequirements) -> Decimal:
    tolerance = req.control_tolerance_f
    if req.temperature_sensitive:
        tolerance -= Decimal("0.5")
        if tolerance < Decimal("0.5"):
            tolerance = Decimal("0.5")
    return _round_tenth(tolerance)


def _warm_side_reduction(transit_hours: int) -> Decimal:
    if transit_hours > 48:
        return Decimal("1.0")
    if transit_hours > 24:
        return Decimal("0.5")
    return ZERO


def _effective_limits(req: ProductTemperatureRequirements) -> tuple[Decimal, Decimal]:
    tolerance = _effective_tolerance(req)
    minimum = _round_tenth(req.minimum_product_f - tolerance)
    maximum = _round_tenth(req.maximum_product_f + tolerance - _warm_side_reduction(req.transit_hours))
    if req.frozen and maximum > FROZEN_MAX_SETPOINT:
        maximum = FROZEN_MAX_SETPOINT
    return minimum, maximum


def evaluate_temperature_compliance_check(
    plan: PlannedSetpointRange,
    req: ProductTemperatureRequirements = ProductTemperatureRequirements(
        minimum_product_f=Decimal("34.0"),
        maximum_product_f=Decimal("38.0"),
        transit_hours=0,
    ),
) -> TemperatureComplianceResult:
    """Evaluate whether a planned setpoint range complies with tender rules.

    The planned minimum and maximum setpoints must both fall inside the computed
    effective setpoint limits. Limits are inclusive and rounded to the nearest
    tenth before comparison.
    """
    _validate(plan, req)
    effective_min, effective_max = _effective_limits(req)

    if plan.minimum_f < effective_min:
        return TemperatureComplianceResult(False, effective_min, effective_max, "below_min_limit")
    if plan.maximum_f > effective_max:
        return TemperatureComplianceResult(False, effective_min, effective_max, "above_max_limit")
    if req.frozen and plan.maximum_f > FROZEN_MAX_SETPOINT:
        return TemperatureComplianceResult(False, effective_min, effective_max, "frozen_cap_exceeded")
    return TemperatureComplianceResult(True, effective_min, effective_max, "compliant")
