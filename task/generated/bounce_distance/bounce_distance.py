"""Bounce distance for repositioning after delivery.

A bounce is the planning miles from the delivery stop to where the tractor is likely to
seek its next revenue opportunity. Tidewater uses this estimate in margin reviews and in
post-audit scorecards. The standard rules are:

- Start from loaded miles between the delivery and the candidate next origin.
- Very short local moves under 8.0 miles are treated as zero bounce.
- Add a fixed terminal approach allowance when the truck is sent to a terminal instead of
  directly to freight.
- Dense urban deliveries add a congestion factor; remote deliveries add a rural factor.
- If the next opportunity begins inside a prebook window, planners usually deadhead more
  efficiently, so subtract a planning credit.
- Empty miles are never negative, are rounded to the nearest tenth mile, and are capped.
- Frozen or hazmat trailers are harder to reposition into general freight, so add equipment
  surcharges. Company tractors can use private yards more efficiently and get a small credit.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

TENTH = Decimal("0.1")
ZERO = Decimal("0.0")
SHORT_HAUL_FLOOR = Decimal("8.0")
DEFAULT_TERMINAL_ALLOWANCE = Decimal("12.0")
DEFAULT_MAX_BOUNCE = Decimal("250.0")


@dataclass(frozen=True)
class BounceTrip:
    loaded_miles_to_next_origin: Decimal
    to_terminal: bool = False
    market_density: str = "standard"
    equipment_type: str = "dry_van"
    prebook_hours: int | None = None
    company_tractor: bool = False


@dataclass(frozen=True)
class BounceRules:
    short_haul_floor: Decimal = SHORT_HAUL_FLOOR
    terminal_allowance: Decimal = DEFAULT_TERMINAL_ALLOWANCE
    max_bounce: Decimal = DEFAULT_MAX_BOUNCE
    urban_factor: Decimal = Decimal("1.15")
    remote_factor: Decimal = Decimal("1.10")
    standard_factor: Decimal = Decimal("1.00")
    prebook_credit: Decimal = Decimal("7.5")
    frozen_surcharge: Decimal = Decimal("18.0")
    hazmat_surcharge: Decimal = Decimal("10.0")
    company_credit: Decimal = Decimal("3.0")


def _validate(trip: BounceTrip, rules: BounceRules) -> None:
    if trip.loaded_miles_to_next_origin < ZERO:
        raise ValueError("loaded_miles_to_next_origin cannot be negative")
    if trip.market_density not in {"urban", "standard", "remote"}:
        raise ValueError(f"unsupported market_density: {trip.market_density}")
    if trip.equipment_type not in {"dry_van", "reefer", "hazmat"}:
        raise ValueError(f"unsupported equipment_type: {trip.equipment_type}")
    if trip.prebook_hours is not None and trip.prebook_hours < 0:
        raise ValueError("prebook_hours cannot be negative")
    if rules.short_haul_floor < ZERO or rules.terminal_allowance < ZERO or rules.max_bounce < ZERO:
        raise ValueError("rule distances must be non-negative")


def _market_factor(trip: BounceTrip, rules: BounceRules) -> Decimal:
    if trip.market_density == "urban":
        return rules.urban_factor
    if trip.market_density == "remote":
        return rules.remote_factor
    return rules.standard_factor


def _equipment_adjustment(trip: BounceTrip, rules: BounceRules) -> Decimal:
    if trip.equipment_type == "reefer":
        return rules.frozen_surcharge
    if trip.equipment_type == "hazmat":
        return rules.hazmat_surcharge
    return ZERO


def _planning_credit(trip: BounceTrip, rules: BounceRules) -> Decimal:
    credit = ZERO
    if trip.prebook_hours is not None and trip.prebook_hours <= 6:
        credit += rules.prebook_credit
    if trip.company_tractor:
        credit += rules.company_credit
    return credit


def calculate_bounce_distance(trip: BounceTrip, rules: BounceRules = BounceRules()) -> Decimal:
    """Estimated empty repositioning miles, rounded to the nearest tenth.

    Very short local moves below ``rules.short_haul_floor`` are zero unless the truck is
    explicitly sent to a terminal, in which case the terminal approach still applies.

    >>> calculate_bounce_distance(BounceTrip(loaded_miles_to_next_origin=Decimal("50")))
    Decimal('50.0')
    """
    _validate(trip, rules)

    base = ZERO if trip.loaded_miles_to_next_origin < rules.short_haul_floor else trip.loaded_miles_to_next_origin
    adjusted = base * _market_factor(trip, rules)

    if trip.to_terminal:
        adjusted += rules.terminal_allowance

    adjusted += _equipment_adjustment(trip, rules)
    adjusted -= _planning_credit(trip, rules)

    if adjusted < ZERO:
        adjusted = ZERO
    if adjusted > rules.max_bounce:
        adjusted = rules.max_bounce
    return adjusted.quantize(TENTH, rounding=ROUND_HALF_UP)
