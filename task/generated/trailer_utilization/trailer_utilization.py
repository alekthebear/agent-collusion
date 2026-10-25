"""Trailer fleet utilization for weekly planning and customer scorecards.

Tidewater reports trailer utilization as the share of available trailer-days that were
productively loaded during a period. A trailer-day is one trailer available for one day.
The planning team excludes units that were out of service for maintenance from the base,
so utilization is measured against available trailer-days minus maintenance downtime.

Business rules:
- ``loaded_days`` are productive trailer-days and cannot exceed ``available_count * period_days``.
- ``idle_days`` are available but unused trailer-days; they are informational and used for
  consistency checks, but they do not directly change the formula.
- ``maintenance_days`` are trailer-days removed from service and are subtracted from the base.
- Effective capacity is ``available_count * period_days - maintenance_days``.
- If effective capacity is zero, utilization is ``100.00`` when there were no loaded days,
  otherwise the input is invalid because nothing was available to load.
- Loaded days cannot exceed effective capacity.
- To tolerate dispatch timing noise, ``loaded_days + idle_days`` may exceed effective
  capacity by up to 0.5 trailer-day; more than that is invalid.
- Fleets with fewer than 5 trailers are volatile, so utilization is reduced by 2.50 points.
- Fleets with 40 or more trailers and at least 95.00% raw utilization earn a 1.00 point bonus,
  capped at 100.00%.
- Results are rounded half up to two decimals and never below 0.00% or above 100.00%.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
HALF_DAY = Decimal("0.5")
SMALL_FLEET_PENALTY = Decimal("2.50")
LARGE_FLEET_BONUS = Decimal("1.00")
BONUS_THRESHOLD = Decimal("95.00")


@dataclass(frozen=True)
class TrailerUtilizationInput:
    period_days: int
    available_count: int
    loaded_days: Decimal
    idle_days: Decimal
    maintenance_days: Decimal = Decimal("0")


@dataclass(frozen=True)
class UtilizationResult:
    utilization_percent: Decimal
    effective_capacity_days: Decimal
    raw_utilization_percent: Decimal


def _validate_nonnegative(name: str, value: int | Decimal) -> None:
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")


def _quantize_percent(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _capacity_days(data: TrailerUtilizationInput) -> Decimal:
    return Decimal(data.period_days) * Decimal(data.available_count)


def _effective_capacity_days(data: TrailerUtilizationInput) -> Decimal:
    return _capacity_days(data) - data.maintenance_days


def _adjusted_percent(raw_percent: Decimal, available_count: int) -> Decimal:
    adjusted = raw_percent
    if available_count < 5:
        adjusted -= SMALL_FLEET_PENALTY
    elif available_count >= 40 and raw_percent >= BONUS_THRESHOLD:
        adjusted += LARGE_FLEET_BONUS
    if adjusted < Decimal("0"):
        return Decimal("0.00")
    if adjusted > Decimal("100"):
        return Decimal("100.00")
    return _quantize_percent(adjusted)


def calculate_trailer_utilization(
    data: TrailerUtilizationInput,
) -> UtilizationResult:
    """Compute trailer utilization percent for a reporting period.

    The result reports both the adjusted scorecard percentage and the raw percentage
    before small-fleet penalties or large-fleet bonuses.
    """
    _validate_nonnegative("period_days", data.period_days)
    _validate_nonnegative("available_count", data.available_count)
    _validate_nonnegative("loaded_days", data.loaded_days)
    _validate_nonnegative("idle_days", data.idle_days)
    _validate_nonnegative("maintenance_days", data.maintenance_days)

    capacity = _capacity_days(data)
    if data.loaded_days > capacity:
        raise ValueError("loaded_days cannot exceed total capacity")
    if data.maintenance_days > capacity:
        raise ValueError("maintenance_days cannot exceed total capacity")

    effective_capacity = _effective_capacity_days(data)
    if effective_capacity < 0:
        raise ValueError("effective capacity cannot be negative")
    if effective_capacity == 0:
        if data.loaded_days == 0:
            return UtilizationResult(
                utilization_percent=Decimal("100.00"),
                effective_capacity_days=Decimal("0"),
                raw_utilization_percent=Decimal("100.00"),
            )
        raise ValueError("loaded_days must be zero when effective capacity is zero")

    if data.loaded_days > effective_capacity:
        raise ValueError("loaded_days cannot exceed effective capacity")

    accounted = data.loaded_days + data.idle_days
    if accounted - effective_capacity > HALF_DAY:
        raise ValueError("loaded_days plus idle_days exceeds effective capacity")

    raw_percent = _quantize_percent((data.loaded_days / effective_capacity) * Decimal("100"))
    adjusted = _adjusted_percent(raw_percent, data.available_count)
    return UtilizationResult(
        utilization_percent=adjusted,
        effective_capacity_days=effective_capacity,
        raw_utilization_percent=raw_percent,
    )
