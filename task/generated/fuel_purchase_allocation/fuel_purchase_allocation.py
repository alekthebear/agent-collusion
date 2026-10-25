"""Allocate fuel purchases to trips for IFTA and settlement reporting.

The settlement service receives one fuel receipt at a time and assigns it to the
trip or jurisdiction records that consumed the fuel. The standard rules are:

* A receipt can only allocate to trips whose date span includes the purchase date.
* Trips with invalid odometer spans are rejected.
* If a receipt names a matching jurisdiction, allocate there first using the lesser
  of purchased gallons and that jurisdiction's estimated gallons.
* Remaining gallons are allocated across eligible trips in proportion to miles.
* When a truck's average MPG is poor (below 4.5), estimated consumption is inflated
  by 3% for proportional allocation; when very efficient (above 8.5), reduced by 2%.
* Company-card purchases under 1.00 gallon are ignored as void-at-pump reversals.
* Final allocations are rounded to 0.01 gallon with half-up rounding. Any rounding
  remainder is placed on the largest eligible share, or the jurisdiction match if one
  exists, so the returned gallons always sum to the billed gallons considered.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
MIN_VOID_GALLONS = Decimal("1.00")
LOW_MPG = Decimal("4.5")
HIGH_MPG = Decimal("8.5")
LOW_FACTOR = Decimal("1.03")
HIGH_FACTOR = Decimal("0.98")


@dataclass(frozen=True)
class TripSpan:
    trip_id: str
    start_date: date
    end_date: date
    start_odometer: int
    end_odometer: int
    jurisdiction: str


@dataclass(frozen=True)
class FuelPurchase:
    purchase_date: date
    gallons: Decimal
    jurisdiction: str | None = None
    is_company_card: bool = True


@dataclass(frozen=True)
class Allocation:
    trip_id: str
    gallons: Decimal


def _validate_trip(trip: TripSpan) -> None:
    if trip.end_date < trip.start_date:
        raise ValueError(f"trip {trip.trip_id} ends before it starts")
    if trip.end_odometer < trip.start_odometer:
        raise ValueError(f"trip {trip.trip_id} odometer decreases")


def _eligible_trips(trips: list[TripSpan], purchase_date: date) -> list[TripSpan]:
    eligible = []
    for trip in trips:
        _validate_trip(trip)
        if trip.start_date <= purchase_date <= trip.end_date:
            eligible.append(trip)
    return eligible


def _miles(trip: TripSpan) -> int:
    return trip.end_odometer - trip.start_odometer


def _estimated_gallons(miles: int, avg_mpg: Decimal) -> Decimal:
    est = Decimal(miles) / avg_mpg
    if avg_mpg < LOW_MPG:
        est *= LOW_FACTOR
    elif avg_mpg > HIGH_MPG:
        est *= HIGH_FACTOR
    return est


def _round(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def allocate_fuel_purchases(
    purchase: FuelPurchase, trips: list[TripSpan], average_mpg: Decimal
) -> list[Allocation]:
    """Allocate one fuel purchase across eligible trips.

    Returns allocations only for trips receiving more than 0.00 gallons.
    """
    if purchase.gallons < 0:
        raise ValueError("gallons cannot be negative")
    if average_mpg <= 0:
        raise ValueError("average_mpg must be positive")
    if purchase.is_company_card and purchase.gallons < MIN_VOID_GALLONS:
        return []

    eligible = _eligible_trips(trips, purchase.purchase_date)
    if not eligible or purchase.gallons == 0:
        return []

    gallons = _round(purchase.gallons)
    shares: dict[str, Decimal] = {trip.trip_id: Decimal("0.00") for trip in eligible}
    preferred_trip_id: str | None = None

    if purchase.jurisdiction is not None:
        matches = [trip for trip in eligible if trip.jurisdiction == purchase.jurisdiction]
        if len(matches) == 1:
            match = matches[0]
            preferred_trip_id = match.trip_id
            actual = min(gallons, _estimated_gallons(_miles(match), average_mpg))
            shares[match.trip_id] = _round(actual)
            gallons -= shares[match.trip_id]
            eligible = [trip for trip in eligible if trip.trip_id != match.trip_id]

    if gallons > 0 and eligible:
        weighted: list[tuple[TripSpan, Decimal]] = []
        total_weight = Decimal("0")
        for trip in eligible:
            miles = _miles(trip)
            weight = _estimated_gallons(miles, average_mpg) if miles > 0 else Decimal("0")
            weighted.append((trip, weight))
            total_weight += weight

        if total_weight == 0:
            first = eligible[0].trip_id
            shares[first] += gallons
        else:
            allocated = Decimal("0.00")
            for trip, weight in weighted:
                portion = _round(gallons * weight / total_weight)
                shares[trip.trip_id] += portion
                allocated += portion
            remainder = gallons - allocated
            if remainder != 0:
                target = preferred_trip_id
                if target is None:
                    target = max(weighted, key=lambda item: (item[1], item[0].trip_id))[0].trip_id
                shares[target] += remainder

    result = [Allocation(trip_id=trip_id, gallons=amt) for trip_id, amt in shares.items() if amt > 0]
    return sorted(result, key=lambda item: item.trip_id)
