"""Federal axle weight checks for a loaded tractor-trailer (23 CFR 658.17).

Load planning runs ``check_axle_weights`` on the scale ticket or the planned axle
loads before a truck is dispatched onto the Interstate. The federal limits:

- 20,000 lbs on any single axle.
- 34,000 lbs on a tandem (two axles more than 40" and at most 96" apart).
- 80,000 lbs gross.
- The bridge formula, W = 500 * (L*N/(N-1) + 12*N + 36), on every group of two or
  more consecutive axles: N is the number of axles in the group, L the distance
  in feet between its outer axles, W the most the group may carry. Like the
  published bridge table, W is rounded to the nearest 500 lbs. A group that is
  just one tandem is covered by the tandem limit instead.
- Exception: two consecutive tandems may carry 34,000 lbs each (68,000 together)
  if their outer axles are 36 feet or more apart, even when the formula gives
  less.

Axles are given front to back, with positions in feet from the steer axle.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

SINGLE_LIMIT = 20_000
TANDEM_LIMIT = 34_000
GROSS_LIMIT = 80_000
TANDEM_MAX_SPACING_FT = 8.0
DOUBLE_TANDEM_MIN_SPAN_FT = 36.0
DOUBLE_TANDEM_LIMIT = 68_000


@dataclass(frozen=True)
class Violation:
    rule: str  # "single", "tandem", "gross" or "bridge"
    first_axle: int
    last_axle: int
    weight: int
    limit: int


def bridge_limit(span_ft: float, axles: int) -> int:
    """The bridge formula for ``axles`` axles spread over ``span_ft`` feet."""
    if axles < 2:
        raise ValueError("the bridge formula needs at least two axles")
    raw = 500 * (Decimal(str(span_ft)) * axles / (axles - 1) + 12 * axles + 36)
    return int((raw / 500).quantize(Decimal(1), rounding=ROUND_HALF_UP) * 500)


def _tandem_starts(positions: list[float]) -> set[int]:
    """Indexes of axles that are the front axle of a tandem."""
    return {
        i for i in range(len(positions) - 1)
        if positions[i + 1] - positions[i] <= TANDEM_MAX_SPACING_FT
    }


def _bridge_spans(axle_count: int) -> list[tuple[int, int]]:
    """The groups the bridge formula is checked on: the outer bridge, steer to last axle.

    Interior groups are already held down by the single and tandem limits.
    """
    return [(0, axle_count - 1)]


def _span_limit(first: int, last: int, positions: list[float], tandems: set[int]) -> int:
    span = positions[last] - positions[first]
    limit = bridge_limit(span, last - first + 1)
    double_tandem = last - first == 3 and first in tandems and first + 2 in tandems
    if double_tandem and span >= DOUBLE_TANDEM_MIN_SPAN_FT:
        limit = max(limit, DOUBLE_TANDEM_LIMIT)
    return limit


def check_axle_weights(weights: list[int], positions: list[float]) -> list[Violation]:
    """Every federal limit the axle loads break; an empty list means legal."""
    if len(weights) != len(positions) or len(weights) < 2:
        raise ValueError("need a weight and a position for each of at least two axles")
    if any(b <= a for a, b in zip(positions, positions[1:])):
        raise ValueError("axle positions must increase front to back")
    tandems = _tandem_starts(positions)
    in_tandem = tandems | {i + 1 for i in tandems}
    violations = []
    for i, weight in enumerate(weights):
        if i not in in_tandem and weight > SINGLE_LIMIT:
            violations.append(Violation("single", i, i, weight, SINGLE_LIMIT))
    for i in sorted(tandems):
        weight = weights[i] + weights[i + 1]
        if weight > TANDEM_LIMIT:
            violations.append(Violation("tandem", i, i + 1, weight, TANDEM_LIMIT))
    gross = sum(weights)
    if gross > GROSS_LIMIT:
        violations.append(Violation("gross", 0, len(weights) - 1, gross, GROSS_LIMIT))
    for first, last in _bridge_spans(len(weights)):
        weight = sum(weights[first:last + 1])
        limit = _span_limit(first, last, positions, tandems)
        if weight > limit:
            violations.append(Violation("bridge", first, last, weight, limit))
    return violations
