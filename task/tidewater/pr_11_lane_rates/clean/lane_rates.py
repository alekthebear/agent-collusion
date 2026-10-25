"""Contract lane rate lookup with fallbacks.

Customer contracts price linehaul per mile by lane. Pricing loads them at three
levels of detail, most specific first:

    zip3        origin ZIP3 -> destination ZIP3   ("972" -> "837")
    zip3_state  origin ZIP3 -> destination state  ("972" -> "ID")
    state       origin state -> destination state ("OR" -> "ID")

Every rate has an effective date and an optional expiry date (inclusive). Rates
get renegotiated lane by lane, so the specific lanes often lapse before the
state-level rates do. A lookup uses the most specific level that has a rate in
effect on the ship date, and falls back to the customer's default per-mile rate
when no level does. If two rates at one level are in effect at once, the one with
the later effective date wins: it is the newer contract amendment.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

LEVELS = ("zip3", "zip3_state", "state")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class LaneRate:
    level: str
    origin: str
    dest: str
    rate_per_mile: Decimal
    effective: date
    expires: date | None = None


@dataclass(frozen=True)
class Shipment:
    origin_zip: str
    origin_state: str
    dest_zip: str
    dest_state: str
    ship_date: date


@dataclass(frozen=True)
class RateMatch:
    rate_per_mile: Decimal
    level: str


RateTable = dict[tuple[str, str, str], list[LaneRate]]


def build_rate_table(rates: list[LaneRate]) -> RateTable:
    table: RateTable = {}
    for rate in rates:
        if rate.level not in LEVELS:
            raise ValueError(f"unknown lane level {rate.level!r}")
        table.setdefault((rate.level, rate.origin, rate.dest), []).append(rate)
    return table


def _candidate_keys(shipment: Shipment) -> list[tuple[str, str, str]]:
    origin3, dest3 = shipment.origin_zip[:3], shipment.dest_zip[:3]
    return [
        ("zip3", origin3, dest3),
        ("zip3_state", origin3, shipment.dest_state),
        ("state", shipment.origin_state, shipment.dest_state),
    ]


def _in_effect(rates: list[LaneRate], on: date) -> list[LaneRate]:
    return [r for r in rates if r.effective <= on and (r.expires is None or on <= r.expires)]


def _most_specific(table: RateTable, shipment: Shipment) -> tuple[str | None, list[LaneRate]]:
    """The most specific level with a rate in effect on the ship date, and those rates."""
    for key in _candidate_keys(shipment):
        live = _in_effect(table.get(key, []), shipment.ship_date)
        if live:
            return key[0], live
    return None, []


def lookup_lane_rate(
    table: RateTable, shipment: Shipment, default_rate: Decimal | None = None
) -> RateMatch:
    """The per-mile rate for ``shipment``, and which level it came from.

    Raises LookupError if no lane rate applies and the customer has no default.
    """
    level, live = _most_specific(table, shipment)
    if live:
        newest = max(live, key=lambda rate: rate.effective)
        return RateMatch(newest.rate_per_mile, level)
    if default_rate is None:
        raise LookupError(f"no lane rate for {shipment.origin_zip} -> {shipment.dest_zip}")
    return RateMatch(default_rate, "default")


def linehaul(table: RateTable, shipment: Shipment, miles: Decimal, default_rate: Decimal | None = None) -> Decimal:
    """Linehaul dollars for the shipment's miles, rounded to the cent."""
    rate = lookup_lane_rate(table, shipment, default_rate).rate_per_mile
    return (rate * miles).quantize(CENT, rounding=ROUND_HALF_UP)
