"""Estimate reefer fuel burned for one trailer operating window.

Business rules mirror Tidewater's settlement estimates for refrigerated trailers.
Fuel burn starts from a trailer-family base gallons-per-hour table by operating mode.
That base rate is adjusted for how hard the unit must work against ambient conditions:
colder setpoints and hotter ambients increase burn. Frozen freight uses the frozen table
when the setpoint is at or below 28 F; otherwise chilled rules apply. Continuous mode
bills all run hours. Start-stop mode assumes cycling losses: for short windows under two
hours, at least 1.2 engine hours are billed; for longer windows only 72% of reported run
hours are treated as engine-on time, with a floor of 1.2 hours. Defrost adds a fixed fuel
allowance by ambient band. Poor door discipline adds an extra 8% burn when door-open
minutes exceed 45. High-altitude mountain lanes above 5,000 ft add 5% because the unit
runs less efficiently. Final fuel is rounded half up to the nearest hundredth gallon.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
SHORT_WINDOW_HOURS = Decimal("2.0")
MIN_START_STOP_ENGINE_HOURS = Decimal("1.2")
START_STOP_DUTY_FACTOR = Decimal("0.72")
DOOR_MINUTES_SURCHARGE_THRESHOLD = 45
DOOR_SURCHARGE_FACTOR = Decimal("1.08")
ALTITUDE_THRESHOLD_FEET = 5000
ALTITUDE_FACTOR = Decimal("1.05")

BASE_RATES = {
    "standard": {
        "continuous": {"chilled": Decimal("0.72"), "frozen": Decimal("1.08")},
        "start_stop": {"chilled": Decimal("0.58"), "frozen": Decimal("0.90")},
    },
    "high_efficiency": {
        "continuous": {"chilled": Decimal("0.64"), "frozen": Decimal("0.98")},
        "start_stop": {"chilled": Decimal("0.52"), "frozen": Decimal("0.82")},
    },
}


@dataclass(frozen=True)
class ReeferLoad:
    setpoint_f: int
    ambient_f: int
    mode: str
    run_hours: Decimal
    trailer_family: str = "standard"
    door_open_minutes: int = 0
    altitude_feet: int = 0


@dataclass(frozen=True)
class FuelBurnResult:
    billed_engine_hours: Decimal
    gallons_burned: Decimal


def _validate(load: ReeferLoad) -> None:
    if load.mode not in {"continuous", "start_stop"}:
        raise ValueError(f"unsupported mode {load.mode}")
    if load.trailer_family not in BASE_RATES:
        raise ValueError(f"unsupported trailer_family {load.trailer_family}")
    if load.run_hours < 0:
        raise ValueError("run_hours cannot be negative")
    if load.door_open_minutes < 0:
        raise ValueError("door_open_minutes cannot be negative")
    if load.altitude_feet < 0:
        raise ValueError("altitude_feet cannot be negative")


def _product_class(setpoint_f: int) -> str:
    return "frozen" if setpoint_f <= 28 else "chilled"


def _base_rate(load: ReeferLoad) -> Decimal:
    product = _product_class(load.setpoint_f)
    return BASE_RATES[load.trailer_family][load.mode][product]


def _ambient_factor(setpoint_f: int, ambient_f: int) -> Decimal:
    spread = ambient_f - setpoint_f
    if spread <= 0:
        return Decimal("0.92")
    if spread <= 20:
        return Decimal("1.00")
    if spread <= 40:
        return Decimal("1.12")
    return Decimal("1.25")


def _engine_hours(load: ReeferLoad) -> Decimal:
    if load.mode == "continuous":
        return load.run_hours
    if load.run_hours == 0:
        return Decimal("0.0")
    if load.run_hours < SHORT_WINDOW_HOURS:
        return MIN_START_STOP_ENGINE_HOURS
    reduced = load.run_hours * START_STOP_DUTY_FACTOR
    return reduced if reduced > MIN_START_STOP_ENGINE_HOURS else MIN_START_STOP_ENGINE_HOURS


def _defrost_gallons(setpoint_f: int, ambient_f: int) -> Decimal:
    if setpoint_f > 28:
        return Decimal("0.00")
    if ambient_f >= 80:
        return Decimal("0.35")
    if ambient_f >= 50:
        return Decimal("0.20")
    return Decimal("0.10")


def _apply_operating_surcharges(gallons: Decimal, door_open_minutes: int, altitude_feet: int) -> Decimal:
    if door_open_minutes > DOOR_MINUTES_SURCHARGE_THRESHOLD:
        gallons *= DOOR_SURCHARGE_FACTOR
    if altitude_feet > ALTITUDE_THRESHOLD_FEET:
        gallons *= ALTITUDE_FACTOR
    return gallons


def calculate_reefer_fuel_burn(load: ReeferLoad) -> FuelBurnResult:
    """Return billed engine hours and estimated gallons burned.

    >>> calculate_reefer_fuel_burn(ReeferLoad(setpoint_f=34, ambient_f=90, mode="continuous", run_hours=Decimal("10"))).gallons_burned
    Decimal('9.00')
    """
    _validate(load)
    hours = _engine_hours(load)
    if hours == 0:
        return FuelBurnResult(billed_engine_hours=Decimal("0.0"), gallons_burned=Decimal("0.00"))
    gallons = _base_rate(load) * _ambient_factor(load.setpoint_f, load.ambient_f) * hours
    gallons += _defrost_gallons(load.setpoint_f, load.ambient_f)
    gallons = _apply_operating_surcharges(gallons, load.door_open_minutes, load.altitude_feet)
    gallons = gallons.quantize(CENT, rounding=ROUND_HALF_UP)
    return FuelBurnResult(billed_engine_hours=hours, gallons_burned=gallons)
