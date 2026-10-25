"""Empty-mile calculation for dispatch settlement and customer scorecards.

Empty miles are non-revenue miles a tractor drives before the first loaded mile and
between loaded segments when a load requires a break in the loaded route. Tidewater's
planning team uses the rules below to keep billing and operations consistent.

Business rules:
- Deadhead from the tractor's start position to the first pickup is billed as empty,
  but ignored when it is less than or equal to a local-yard threshold.
- A relay or yard move between loaded segments counts as empty only when the gap is
  above the same local threshold.
- Empty miles are rounded to the nearest whole mile using half-up rounding after all
  adjustments, not per leg.
- Team drivers get a small efficiency credit on repositioning miles only; the credit
  does not reduce start deadhead.
- Hazardous loads require a safety buffer added to every counted empty leg.
- If a segment is cancelled after dispatch, the tractor still may have moved toward it;
  the approach miles are counted at 50%.
- Border-crossing loads have 3 administrative miles added once when any empty miles are
  counted.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENTRAL_THRESHOLD = Decimal("7.0")
TEAM_RELAY_DISCOUNT = Decimal("0.90")
HAZMAT_BUFFER = Decimal("2.5")
BORDER_ADMIN_MILES = Decimal("3.0")
WHOLE_MILE = Decimal("1")


@dataclass(frozen=True)
class LoadContext:
    start_deadhead_miles: Decimal
    border_crossing: bool = False
    team_driver: bool = False
    hazardous: bool = False


@dataclass(frozen=True)
class LoadedSegment:
    loaded_miles: Decimal
    reposition_miles_after: Decimal = Decimal("0")
    cancelled_after_dispatch: bool = False


def _validate(context: LoadContext, segments: tuple[LoadedSegment, ...]) -> None:
    if context.start_deadhead_miles < 0:
        raise ValueError("start_deadhead_miles cannot be negative")
    if not segments:
        raise ValueError("at least one segment is required")
    for segment in segments:
        if segment.loaded_miles <= 0:
            raise ValueError("loaded_miles must be positive")
        if segment.reposition_miles_after < 0:
            raise ValueError("reposition_miles_after cannot be negative")


def _counted_leg(miles: Decimal, hazardous: bool) -> Decimal:
    if miles <= CENTRAL_THRESHOLD:
        return Decimal("0")
    counted = miles
    if hazardous:
        counted += HAZMAT_BUFFER
    return counted


def _start_empty_miles(context: LoadContext) -> Decimal:
    return _counted_leg(context.start_deadhead_miles, context.hazardous)


def _reposition_empty_miles(segment: LoadedSegment, context: LoadContext) -> Decimal:
    counted = _counted_leg(segment.reposition_miles_after, context.hazardous)
    if counted == 0:
        return counted
    if segment.cancelled_after_dispatch:
        counted *= Decimal("0.50")
    if context.team_driver:
        counted *= TEAM_RELAY_DISCOUNT
    return counted


def calculate_empty_miles(
    context: LoadContext, segments: tuple[LoadedSegment, ...]
) -> Decimal:
    """Return settlement empty miles as a whole number of miles.

    The result is rounded once at the end to the nearest mile using half-up rules.

    >>> from decimal import Decimal
    >>> ctx = LoadContext(start_deadhead_miles=Decimal('12'), team_driver=True)
    >>> segs = (LoadedSegment(loaded_miles=Decimal('100'), reposition_miles_after=Decimal('10')),)
    >>> calculate_empty_miles(ctx, segs)
    Decimal('21')
    """
    _validate(context, segments)

    total = _start_empty_miles(context)
    for segment in segments:
        total += _reposition_empty_miles(segment, context)

    if total == 0:
        return Decimal("0")
    if context.border_crossing:
        total += BORDER_ADMIN_MILES
    return total.quantize(WHOLE_MILE, rounding=ROUND_HALF_UP)
