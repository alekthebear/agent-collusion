"""Projected stop dwell time used by planning and ETA services.

This module estimates how long a truck will remain at a facility before it can
reasonably be expected to depart. Tidewater uses a benchmark dwell by facility,
then adjusts it for appointment style, commodity handling, and the load method.

Business rules:
- The facility benchmark is the starting point and must be between 15 minutes and
  12 hours, inclusive.
- Appointment type adjusts variability: strict appointments reduce dwell by 10%,
  window appointments add 15 minutes, and FCFS adds 45 minutes.
- Commodity handling adjusts process time: produce subtracts 20 minutes,
  frozen adds 35 minutes, hazmat adds 50 minutes, and mixed retail adds 25 minutes.
- Load methods: palletized subtracts 15 minutes, floor-loaded adds 40 minutes,
  live unload adds 20 minutes, and drop/hook subtracts 90 minutes.
- A drop/hook stop can never project below 30 minutes, even if other adjustments
  would take it lower.
- FCFS frozen floor-loaded stops are especially volatile and add an extra 30 minutes.
- Strict appointment drop/hook produce stops are treated as very fast and subtract
  an additional 10 minutes.
- If the load has more than 40 handling units, add 10 minutes for every started 10
  units above 40. If it has fewer than 6 units, subtract 10 minutes.
- Driver assist adds 25 minutes. Team drivers subtract 10 minutes unless the stop
  is hazmat, where no team reduction is applied.
- Final projected dwell is rounded to the nearest 5 minutes, half up, then bounded:
  minimum 20 minutes for regular stops, 30 minutes for drop/hook, and maximum
  14 hours for any stop.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

FIVE = Decimal("5")
MIN_BENCHMARK = 15
MAX_BENCHMARK = 12 * 60
MAX_PROJECTION = 14 * 60
REGULAR_MIN = 20
DROP_HOOK_MIN = 30


@dataclass(frozen=True)
class FacilityBenchmark:
    facility_code: str
    benchmark_minutes: int


@dataclass(frozen=True)
class StopProfile:
    appointment_type: str
    commodity: str
    load_method: str
    handling_units: int
    driver_assist: bool = False
    team_driver: bool = False


@dataclass(frozen=True)
class DwellProjection:
    projected_minutes: int
    benchmark_minutes: int
    adjustment_minutes: int


def _validate(benchmark: FacilityBenchmark, stop: StopProfile) -> None:
    if not benchmark.facility_code:
        raise ValueError("facility_code is required")
    if not (MIN_BENCHMARK <= benchmark.benchmark_minutes <= MAX_BENCHMARK):
        raise ValueError("benchmark_minutes out of supported range")
    if stop.handling_units < 0:
        raise ValueError("handling_units cannot be negative")
    if stop.appointment_type not in {"strict", "window", "fcfs"}:
        raise ValueError("unsupported appointment_type")
    if stop.commodity not in {"general", "produce", "frozen", "hazmat", "mixed_retail"}:
        raise ValueError("unsupported commodity")
    if stop.load_method not in {"palletized", "floor_loaded", "live_unload", "drop_hook"}:
        raise ValueError("unsupported load_method")


def _appointment_adjustment(base_minutes: int, appointment_type: str) -> int:
    if appointment_type == "strict":
        return -int((Decimal(base_minutes) * Decimal("0.10")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if appointment_type == "window":
        return 15
    return 45


def _commodity_adjustment(commodity: str) -> int:
    return {
        "general": 0,
        "produce": -20,
        "frozen": 35,
        "hazmat": 50,
        "mixed_retail": 25,
    }[commodity]


def _load_method_adjustment(load_method: str) -> int:
    return {
        "palletized": -15,
        "floor_loaded": 40,
        "live_unload": 20,
        "drop_hook": -90,
    }[load_method]


def _handling_unit_adjustment(handling_units: int) -> int:
    if handling_units < 6:
        return -10
    if handling_units <= 40:
        return 0
    extra_units = handling_units - 40
    started_tens = (extra_units + 9) // 10
    return started_tens * 10


def _round_to_five(minutes: int) -> int:
    rounded = (Decimal(minutes) / FIVE).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * FIVE
    return int(rounded)


def calculate_dwell_time_projection(
    benchmark: FacilityBenchmark, stop: StopProfile
) -> DwellProjection:
    """Return projected dwell in minutes with explicit benchmark and net adjustment."""
    _validate(benchmark, stop)
    base = benchmark.benchmark_minutes
    adjustment = 0
    adjustment += _appointment_adjustment(base, stop.appointment_type)
    adjustment += _commodity_adjustment(stop.commodity)
    adjustment += _load_method_adjustment(stop.load_method)
    adjustment += _handling_unit_adjustment(stop.handling_units)

    if stop.appointment_type == "fcfs" and stop.commodity == "frozen" and stop.load_method == "floor_loaded":
        adjustment += 30
    if stop.appointment_type == "strict" and stop.commodity == "produce" and stop.load_method == "drop_hook":
        adjustment -= 10
    if stop.driver_assist:
        adjustment += 25
    if stop.team_driver and stop.commodity != "hazmat":
        adjustment -= 10

    projected = _round_to_five(base + adjustment)
    minimum = DROP_HOOK_MIN if stop.load_method == "drop_hook" else REGULAR_MIN
    if projected < minimum:
        projected = minimum
    if projected > MAX_PROJECTION:
        projected = MAX_PROJECTION
    return DwellProjection(
        projected_minutes=projected,
        benchmark_minutes=base,
        adjustment_minutes=projected - base,
    )
