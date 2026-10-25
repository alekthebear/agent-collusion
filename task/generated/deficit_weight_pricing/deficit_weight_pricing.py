"""Deficit weight pricing for LTL shipments.

A shipment may rate at a lower hundredweight (CWT) price if buying weight up to the
next published break produces a lower total linehaul charge than rating the actual
weight. The rating engine compares:

* actual-weight pricing at the current break, and
* deficit pricing at the immediate next break, using that break's minimum weight.

Business rules used by Tidewater Freight:
- Weight breaks are inclusive minimums in pounds and must be ordered ascending.
- Weights at or below zero are invalid.
- The first break is the floor for all weights below the next minimum.
- If actual weight is exactly on a break minimum, there is no deficit to buy.
- A shipment is only deficit-rated to the immediate next break, never skipping ahead.
- If the gap to the next break exceeds ``max_deficit_pounds``, deficit pricing is not allowed.
- If the shipment is marked ``density_exempt``, deficit pricing is not allowed.
- Charges are computed as ``(rated_weight / 100) * rate_per_cwt`` and rounded half up
  to cents after the multiplication.
- If actual and deficit totals tie, actual-weight pricing applies.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
HUNDRED = Decimal("100")
DEFAULT_MAX_DEFICIT_POUNDS = 499


@dataclass(frozen=True)
class WeightBreak:
    minimum_weight: int
    rate_per_cwt: Decimal


@dataclass(frozen=True)
class DeficitPricingInput:
    actual_weight: int
    breaks: tuple[WeightBreak, ...]
    max_deficit_pounds: int = DEFAULT_MAX_DEFICIT_POUNDS
    density_exempt: bool = False


def _validate(data: DeficitPricingInput) -> None:
    if data.actual_weight <= 0:
        raise ValueError("actual_weight must be positive")
    if data.max_deficit_pounds < 0:
        raise ValueError("max_deficit_pounds cannot be negative")
    if not data.breaks:
        raise ValueError("at least one weight break is required")
    prev = 0
    for brk in data.breaks:
        if brk.minimum_weight <= 0:
            raise ValueError("break minimums must be positive")
        if brk.minimum_weight <= prev:
            raise ValueError("break minimums must be strictly increasing")
        if brk.rate_per_cwt <= 0:
            raise ValueError("rates must be positive")
        prev = brk.minimum_weight


def _charge(weight: int, rate_per_cwt: Decimal) -> Decimal:
    amount = (Decimal(weight) / HUNDRED) * rate_per_cwt
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _current_break_index(weight: int, breaks: tuple[WeightBreak, ...]) -> int:
    current = 0
    for i, brk in enumerate(breaks):
        if weight >= brk.minimum_weight:
            current = i
        else:
            break
    return current


def _next_break(index: int, breaks: tuple[WeightBreak, ...]) -> WeightBreak | None:
    if index + 1 >= len(breaks):
        return None
    return breaks[index + 1]


def calculate_deficit_weight_pricing(data: DeficitPricingInput) -> Decimal:
    """Return the applicable linehaul amount after considering deficit rating.

    The result is the cheaper of actual-weight rating and the immediate next break's
    minimum-weight rating when deficit pricing is permitted and beneficial.
    """
    _validate(data)
    index = _current_break_index(data.actual_weight, data.breaks)
    current = data.breaks[index]
    actual_amount = _charge(data.actual_weight, current.rate_per_cwt)

    if data.density_exempt:
        return actual_amount
    if data.actual_weight == current.minimum_weight:
        return actual_amount

    nxt = _next_break(index, data.breaks)
    if nxt is None:
        return actual_amount

    deficit_pounds = nxt.minimum_weight - data.actual_weight
    if deficit_pounds <= 0:
        return actual_amount
    if deficit_pounds > data.max_deficit_pounds:
        return actual_amount

    deficit_amount = _charge(nxt.minimum_weight, nxt.rate_per_cwt)
    if deficit_amount < actual_amount:
        return deficit_amount
    return actual_amount
