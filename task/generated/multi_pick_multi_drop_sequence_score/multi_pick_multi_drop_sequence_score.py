"""Route sequence score for multi-pick, multi-drop dispatch comparisons.

The planning desk compares candidate sequences for loads with several pickups and
several deliveries. Lower scores are better. The score combines four business
signals: backtracking miles, service-window pressure, handling complexity, and
expected detention risk.

Rules used by dispatch:
- Backtracking is any miles run beyond the direct corridor from first pickup to
  final delivery. The first 15 excess miles are tolerated with no penalty.
  Remaining backtrack miles score 1.2 points each up to 100 miles, then 1.8
  points each above 100.
- Tight windows add pressure. A stop with a window under 60 minutes scores 12
  points; 60 to 119 minutes scores 5 points. Appointment-required stops add 3
  points each. If every stop has a window of at least 180 minutes, subtract 4
  points for schedule flexibility.
- Handling complexity is based on extra touches. Each pickup after the first
  adds 4 points; each delivery after the first adds 3 points. Hazmat adds 14.
  Refrigerated protection adds 9. If both are present, add a combined-compliance
  bump of 4 more points.
- Detention risk is assessed per stop from expected dwell minutes. The first 45
  minutes at a stop are treated as normal. Minutes 46 to 90 score 0.10 points
  each; any minutes above 90 score 0.18 points each. A stop flagged as known
  congestion adds 6 points.
- Special adjustments: if total stops exceed 6, add 2 points for each stop over
  6. If there are exactly 2 pickups and 2 deliveries and no special handling,
  subtract 2 points as a common efficient pattern.
- The final score is never negative and is rounded to the nearest tenth using
  half-up rounding.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

TENTH = Decimal("0.1")


@dataclass(frozen=True)
class SequenceStop:
    window_minutes: int
    expected_dwell_minutes: int
    appointment_required: bool = False
    known_congestion: bool = False


@dataclass(frozen=True)
class SequencePlan:
    pickup_count: int
    delivery_count: int
    direct_miles: Decimal
    planned_miles: Decimal
    stops: tuple[SequenceStop, ...]
    hazmat: bool = False
    refrigerated: bool = False


def _validate(plan: SequencePlan) -> None:
    if plan.pickup_count < 1 or plan.delivery_count < 1:
        raise ValueError("pickup_count and delivery_count must both be at least 1")
    if plan.direct_miles < 0 or plan.planned_miles < 0:
        raise ValueError("miles cannot be negative")
    if len(plan.stops) != plan.pickup_count + plan.delivery_count:
        raise ValueError("stops must match pickup_count + delivery_count")
    for stop in plan.stops:
        if stop.window_minutes <= 0:
            raise ValueError("window_minutes must be positive")
        if stop.expected_dwell_minutes < 0:
            raise ValueError("expected_dwell_minutes cannot be negative")


def _backtracking_score(direct_miles: Decimal, planned_miles: Decimal) -> Decimal:
    excess = planned_miles - direct_miles
    if excess <= Decimal("15"):
        return Decimal("0")
    chargeable = excess - Decimal("15")
    first_band = min(chargeable, Decimal("100"))
    second_band = max(chargeable - Decimal("100"), Decimal("0"))
    return first_band * Decimal("1.2") + second_band * Decimal("1.8")


def _window_score(stops: tuple[SequenceStop, ...]) -> Decimal:
    score = Decimal("0")
    all_wide = True
    for stop in stops:
        if stop.window_minutes < 60:
            score += Decimal("12")
        elif stop.window_minutes < 120:
            score += Decimal("5")
        if stop.appointment_required:
            score += Decimal("3")
        if stop.window_minutes < 180:
            all_wide = False
    if all_wide:
        score -= Decimal("4")
    return score


def _handling_score(plan: SequencePlan) -> Decimal:
    score = Decimal((plan.pickup_count - 1) * 4 + (plan.delivery_count - 1) * 3)
    if plan.hazmat:
        score += Decimal("14")
    if plan.refrigerated:
        score += Decimal("9")
    if plan.hazmat and plan.refrigerated:
        score += Decimal("4")
    if plan.pickup_count == 2 and plan.delivery_count == 2 and not plan.hazmat and not plan.refrigerated:
        score -= Decimal("2")
    return score


def _detention_score(stops: tuple[SequenceStop, ...]) -> Decimal:
    score = Decimal("0")
    for stop in stops:
        dwell = stop.expected_dwell_minutes
        if dwell > 45:
            first_band = min(dwell, 90) - 45
            score += Decimal(first_band) * Decimal("0.10")
        if dwell > 90:
            score += Decimal(dwell - 90) * Decimal("0.18")
        if stop.known_congestion:
            score += Decimal("6")
    return score


def calculate_multi_pick_multi_drop_sequence_score(plan: SequencePlan) -> Decimal:
    """Return a dispatch comparison score where lower is better.

    The score reflects backtracking, service-window pressure, handling
    complexity, and detention risk. Negative totals are floored at 0.0 and the
    result is rounded to one decimal place using half-up rounding.
    """
    _validate(plan)
    total = (
        _backtracking_score(plan.direct_miles, plan.planned_miles)
        + _window_score(plan.stops)
        + _handling_score(plan)
        + _detention_score(plan.stops)
    )
    stop_overage = max(len(plan.stops) - 6, 0)
    total += Decimal(stop_overage * 2)
    if total < 0:
        total = Decimal("0")
    return total.quantize(TENTH, rounding=ROUND_HALF_UP)
