"""Per-mile tire wear expense for one tractor or trailer tire position.

Tidewater accrues tire expense per mile so settled loads carry a small share of the
expected casing and tread consumption. The planning rules used here are:

* A tire starts with an original purchase cost and expected life in miles.
* A casing may be retreaded up to three times for accrual purposes; extra cycles are
  ignored even if operations record a higher count.
* Each counted retread adds retread cost and additional usable miles equal to 85% of
  the original expected life.
* Position affects wear by changing usable miles, not cost. Steer wears fastest,
  trailer slowest.
* Steer positions do not accrue any retread value; they are treated as original tread
  only, regardless of the recorded retread cycle count.
* Severe service reduces or modestly increases usable miles through a bounded factor.
* Expected life below 10,000 miles is invalid planning data.
* The returned amount is dollars for the requested miles, rounded half up to four
  decimal places.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT_PER_MILE = Decimal("0.0001")
MIN_BASE_LIFE_MILES = 10000
MAX_RETREAD_CYCLES = 3
RETREAD_MILES_FACTOR = Decimal("0.85")
MIN_SERVICE_FACTOR = Decimal("0.50")
MAX_SERVICE_FACTOR = Decimal("1.10")
POSITION_WEAR = {
    "steer": Decimal("0.92"),
    "drive": Decimal("1.00"),
    "trailer": Decimal("1.08"),
    "lift": Decimal("0.95"),
}


@dataclass(frozen=True)
class TireSet:
    purchase_cost: Decimal
    expected_life_miles: int
    retread_cost: Decimal = Decimal("0.00")
    retread_cycles: int = 0


@dataclass(frozen=True)
class TireUsage:
    position: str
    miles_driven: int
    severe_service_factor: Decimal = Decimal("1.00")


def _validate(tire: TireSet, usage: TireUsage) -> None:
    if tire.purchase_cost < 0 or tire.retread_cost < 0:
        raise ValueError("costs must be non-negative")
    if tire.expected_life_miles < MIN_BASE_LIFE_MILES:
        raise ValueError("expected_life_miles is below minimum planning threshold")
    if tire.retread_cycles < 0:
        raise ValueError("retread_cycles cannot be negative")
    if usage.miles_driven < 0:
        raise ValueError("miles_driven cannot be negative")
    if usage.position not in POSITION_WEAR:
        raise ValueError(f"unknown tire position: {usage.position}")
    if not (MIN_SERVICE_FACTOR <= usage.severe_service_factor <= MAX_SERVICE_FACTOR):
        raise ValueError("severe_service_factor is outside supported range")


def _counted_retread_cycles(cycles: int, position: str) -> int:
    if position == "steer":
        return 0
    return min(cycles, MAX_RETREAD_CYCLES)


def _total_cost(tire: TireSet, counted_cycles: int) -> Decimal:
    return tire.purchase_cost + tire.retread_cost * counted_cycles


def _usable_miles(tire: TireSet, usage: TireUsage, counted_cycles: int) -> Decimal:
    base = Decimal(tire.expected_life_miles)
    factor = POSITION_WEAR[usage.position] * usage.severe_service_factor
    original_miles = base * factor
    retread_miles = base * RETREAD_MILES_FACTOR * counted_cycles * factor
    usable = original_miles + retread_miles
    if usable <= 0:
        raise ValueError("usable miles must be positive")
    return usable


def calculate_tire_wear_cost(tire: TireSet, usage: TireUsage) -> Decimal:
    """Return tire wear expense for the given miles, rounded to 4 decimals.

    Lifecycle cost is spread across expected usable miles for the specific tire
    position and service level, then multiplied by ``usage.miles_driven``.
    """
    _validate(tire, usage)
    if usage.miles_driven == 0:
        return Decimal("0.0000")
    counted_cycles = _counted_retread_cycles(tire.retread_cycles, usage.position)
    total_cost = _total_cost(tire, counted_cycles)
    usable_miles = _usable_miles(tire, usage, counted_cycles)
    amount = total_cost * Decimal(usage.miles_driven) / usable_miles
    return amount.quantize(CENT_PER_MILE, rounding=ROUND_HALF_UP)
