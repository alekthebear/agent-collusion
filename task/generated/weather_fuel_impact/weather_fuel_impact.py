"""Expected fuel-consumption uplift caused by weather and terrain on one move.

The planning service uses this estimate to add a small fuel-risk percentage to linehaul
costs before a load is covered. The function returns an uplift percent, not dollars.
Business rules are intentionally simple and deterministic:

- Start from 0.00% uplift and add factors for temperature, wind, precipitation and terrain.
- Temperature: no effect from 32F through 85F inclusive. Below freezing adds more because
  winter blend fuel, idling and rolling resistance tend to rise. Extreme heat above 95F also
  adds a small penalty for refrigeration and engine load.
- Wind uses the absolute sustained speed. Crosswinds are less damaging than headwinds.
  Tailwinds never create a credit; they simply add nothing.
- Precipitation is based on the stronger of rain or snow assumptions. Trace amounts below
  0.01 in/hr are ignored. Snow penalties are larger than rain penalties.
- Terrain is a route planning assumption. Flat has no surcharge; rolling, hilly and mountain
  grades add increasing percentages.
- Equipment type changes sensitivity: refrigerated trailers add 1.25%; straight trucks add
  0.75%; day cabs on short regional work add 0.40%; sleepers and dry vans add no base uplift.
- In severe conditions, add a combined-condition surcharge of 1.00% when sustained wind is at
  least 30 mph and there is measurable precipitation.
- Final uplift is capped at 18.00% and rounded half-up to the nearest hundredth.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
MAX_UPLIFT = Decimal("18.00")


@dataclass(frozen=True)
class WeatherProfile:
    temperature_f: int
    wind_mph: int
    wind_direction: str = "cross"
    precipitation_in_per_hr: Decimal = Decimal("0.00")
    precipitation_type: str = "none"


@dataclass(frozen=True)
class TripAssumptions:
    terrain: str = "flat"
    equipment_type: str = "dry_van"


def _validate(weather: WeatherProfile, trip: TripAssumptions) -> None:
    if weather.wind_mph < 0:
        raise ValueError("wind_mph cannot be negative")
    if weather.precipitation_in_per_hr < 0:
        raise ValueError("precipitation cannot be negative")
    if weather.wind_direction not in {"head", "cross", "tail"}:
        raise ValueError("wind_direction must be head, cross, or tail")
    if weather.precipitation_type not in {"none", "rain", "snow", "mixed"}:
        raise ValueError("invalid precipitation_type")
    if trip.terrain not in {"flat", "rolling", "hilly", "mountain"}:
        raise ValueError("invalid terrain")
    if trip.equipment_type not in {"dry_van", "reefer", "straight_truck", "day_cab", "sleeper"}:
        raise ValueError("invalid equipment_type")
    if weather.precipitation_type == "none" and weather.precipitation_in_per_hr != Decimal("0.00"):
        raise ValueError("precipitation_type none requires zero rate")


def _temperature_uplift(temp_f: int) -> Decimal:
    if temp_f < 0:
        return Decimal("3.00")
    if temp_f < 32:
        return Decimal("1.75")
    if temp_f <= 85:
        return Decimal("0.00")
    if temp_f <= 95:
        return Decimal("0.50")
    return Decimal("1.00")


def _wind_uplift(speed: int, direction: str) -> Decimal:
    if direction == "tail" or speed < 10:
        return Decimal("0.00")
    if speed < 20:
        base = Decimal("0.75")
    elif speed < 30:
        base = Decimal("1.50")
    elif speed < 40:
        base = Decimal("2.50")
    else:
        base = Decimal("3.50")
    if direction == "cross":
        return base - Decimal("0.50")
    return base


def _precipitation_uplift(rate: Decimal, kind: str) -> Decimal:
    if kind == "none" or rate < Decimal("0.01"):
        return Decimal("0.00")
    if kind == "rain":
        if rate < Decimal("0.10"):
            return Decimal("0.50")
        if rate < Decimal("0.30"):
            return Decimal("1.25")
        return Decimal("2.00")
    if kind == "snow":
        if rate < Decimal("0.05"):
            return Decimal("1.50")
        if rate < Decimal("0.15"):
            return Decimal("2.50")
        return Decimal("4.00")
    return Decimal("2.25")


def _terrain_uplift(terrain: str) -> Decimal:
    return {
        "flat": Decimal("0.00"),
        "rolling": Decimal("1.00"),
        "hilly": Decimal("2.00"),
        "mountain": Decimal("3.50"),
    }[terrain]


def _equipment_uplift(equipment_type: str) -> Decimal:
    return {
        "dry_van": Decimal("0.00"),
        "sleeper": Decimal("0.00"),
        "day_cab": Decimal("0.40"),
        "straight_truck": Decimal("0.75"),
        "reefer": Decimal("1.25"),
    }[equipment_type]


def calculate_weather_fuel_impact(
    weather: WeatherProfile, trip: TripAssumptions = TripAssumptions()
) -> Decimal:
    """Return expected fuel-consumption uplift percent for the move.

    The result is a positive percent like Decimal("3.25") for a 3.25% expected uplift.
    """
    _validate(weather, trip)
    total = Decimal("0.00")
    total += _temperature_uplift(weather.temperature_f)
    total += _wind_uplift(weather.wind_mph, weather.wind_direction)
    total += _precipitation_uplift(weather.precipitation_in_per_hr, weather.precipitation_type)
    total += _terrain_uplift(trip.terrain)
    total += _equipment_uplift(trip.equipment_type)
    if weather.wind_mph >= 30 and weather.precipitation_in_per_hr >= Decimal("0.01"):
        total += Decimal("1.00")
    if total > MAX_UPLIFT:
        total = MAX_UPLIFT
    return total.quantize(CENT, rounding=ROUND_HALF_UP)
