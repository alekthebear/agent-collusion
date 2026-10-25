"""Chain-up requirement decisions for mountain routes.

Dispatch uses these rules to decide whether a load must carry out or install tire
chains before entering a mountain pass. A route is chain-required when a state
chain law is active, or when winter weather and elevation together make chains
mandatory under our operating guide. The guide is intentionally conservative:
November through March are winter months, and October/April become winter-like at
higher elevations. Severe icing always requires chains above lowland corridors.

Business rules implemented here:
- If a state chain law is active, chains are required regardless of weather.
- Routes below 1,500 ft never require chains unless state law is active.
- In core winter months (Nov-Mar), chains are required at 4,000 ft or above when
  snow is present, or at 5,500 ft or above with freezing rain.
- In shoulder months (Oct and Apr), those thresholds increase by 1,000 ft.
- Severe icing requires chains at 2,500 ft or above in any month.
- Wind alone does not trigger chains, but at 6,500 ft or above wind plus either
  snow or freezing rain requires chains because blow-over and drift risk rise.
- Borderline elevations count as requiring chains when they meet the threshold.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class WeatherFlags:
    snow: bool = False
    freezing_rain: bool = False
    severe_icing: bool = False
    high_wind: bool = False


@dataclass(frozen=True)
class RouteConditions:
    travel_date: date
    max_elevation_ft: int
    state_chain_law_active: bool = False
    weather: WeatherFlags = WeatherFlags()


def _validate(route: RouteConditions) -> None:
    if route.max_elevation_ft < 0:
        raise ValueError(f"max_elevation_ft {route.max_elevation_ft} cannot be negative")


def _season(route_date: date) -> str:
    month = route_date.month
    if month in {11, 12, 1, 2, 3}:
        return "winter"
    if month in {10, 4}:
        return "shoulder"
    return "summer"


def _snow_threshold(season: str) -> int | None:
    if season == "winter":
        return 4000
    if season == "shoulder":
        return 5000
    return None


def _freezing_rain_threshold(season: str) -> int | None:
    if season == "winter":
        return 5500
    if season == "shoulder":
        return 6500
    return None


def _meets_threshold(elevation_ft: int, threshold: int | None) -> bool:
    return threshold is not None and elevation_ft >= threshold


def calculate_chainup_requirement(route: RouteConditions) -> bool:
    """Return True when chains are required for the route.

    The result is a planning decision only: whether the route should be treated as
    chain-required based on route elevation, season, weather, and active state law.
    """
    _validate(route)

    if route.state_chain_law_active:
        return True

    elevation = route.max_elevation_ft
    weather = route.weather

    if elevation < 1500:
        return False

    if weather.severe_icing and elevation >= 2500:
        return True

    if elevation >= 6500 and weather.high_wind and (weather.snow or weather.freezing_rain):
        return True

    season = _season(route.travel_date)

    if weather.snow and _meets_threshold(elevation, _snow_threshold(season)):
        return True

    if weather.freezing_rain and _meets_threshold(elevation, _freezing_rain_threshold(season)):
        return True

    return False
