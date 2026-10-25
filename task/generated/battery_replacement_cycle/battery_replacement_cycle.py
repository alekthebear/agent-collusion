"""Battery replacement planning for tractors and reefers.

Operations uses this estimate to flag units for preventive battery replacement before
an avoidable no-start or temperature-control failure. The cycle is based on months in
service, observed resting-voltage decline, climate severity, and maintenance findings.

Business rules:
- Start from a 48-month baseline replacement cycle.
- Climate shortens life: mild 0 months, temperate 3, hot 6, severe_cold 8,
  desert 10.
- Steeper voltage decline shortens life based on the average monthly drop in volts:
  under 0.010 V/month adds no penalty, 0.010 to 0.019 shortens 3 months,
  0.020 to 0.034 shortens 7 months, and 0.035 or more shortens 12 months.
- Batteries that repeatedly test low after charging are handled as special cases:
  if latest resting voltage is below 11.80 V, replace now; if below 12.00 V and
  there were at least 2 jump starts in the last 90 days, replace now.
- Preventive maintenance findings shorten the cycle: heavy corrosion 4 months,
  moderate corrosion 2 months, secure terminals 0; if the battery is not secured in
  the tray, shorten 6 months more.
- High-utilization units (at least 26 starts per week) shorten 4 months. Very light
  use (4 or fewer starts per week) extends 2 months unless the climate is desert.
- A rising or flat resting-voltage trend never earns extra life; only decline counts.
- The final cycle is bounded to 12 through 60 months.
- Replacement due status is based on age compared with the computed cycle. Remaining
  months are rounded up to the next whole month so planners do not miss the window.
"""

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal

BASELINE_CYCLE_MONTHS = 48
MIN_CYCLE_MONTHS = 12
MAX_CYCLE_MONTHS = 60


@dataclass(frozen=True)
class BatteryProfile:
    age_months: int
    climate: str
    latest_resting_voltage: Decimal
    prior_resting_voltage: Decimal
    months_between_voltage_samples: int
    jump_starts_last_90_days: int = 0
    corrosion_level: str = "secure"
    tray_secured: bool = True
    starts_per_week: int = 12


@dataclass(frozen=True)
class BatteryReplacementCycle:
    recommended_cycle_months: int
    remaining_months: int
    replace_now: bool


def _validate(profile: BatteryProfile) -> None:
    if profile.age_months < 0:
        raise ValueError("age_months cannot be negative")
    if profile.months_between_voltage_samples <= 0:
        raise ValueError("months_between_voltage_samples must be positive")
    if profile.jump_starts_last_90_days < 0 or profile.starts_per_week < 0:
        raise ValueError("counts cannot be negative")
    if profile.climate not in {"mild", "temperate", "hot", "severe_cold", "desert"}:
        raise ValueError("unknown climate")
    if profile.corrosion_level not in {"secure", "moderate", "heavy"}:
        raise ValueError("unknown corrosion_level")


def _climate_penalty(climate: str) -> int:
    return {"mild": 0, "temperate": 3, "hot": 6, "severe_cold": 8, "desert": 10}[climate]


def _voltage_penalty(latest: Decimal, prior: Decimal, months: int) -> int:
    decline_per_month = (prior - latest) / Decimal(months)
    if decline_per_month <= Decimal("0"):
        return 0
    if decline_per_month < Decimal("0.010"):
        return 0
    if decline_per_month < Decimal("0.020"):
        return 3
    if decline_per_month < Decimal("0.035"):
        return 7
    return 12


def _maintenance_penalty(corrosion_level: str, tray_secured: bool) -> int:
    penalty = {"secure": 0, "moderate": 2, "heavy": 4}[corrosion_level]
    if not tray_secured:
        penalty += 6
    return penalty


def _utilization_adjustment(starts_per_week: int, climate: str) -> int:
    if starts_per_week >= 26:
        return -4
    if starts_per_week <= 4 and climate != "desert":
        return 2
    return 0


def _bounded_cycle(months: int) -> int:
    return max(MIN_CYCLE_MONTHS, min(MAX_CYCLE_MONTHS, months))


def calculate_battery_replacement_cycle(profile: BatteryProfile) -> BatteryReplacementCycle:
    """Return the planned replacement cycle and due status for a battery.

    The recommendation starts from the standard 48-month cycle, applies penalties and
    credits from climate, voltage trend, maintenance findings, and utilization, then
    clamps the result into the 12 to 60 month planning range.
    """
    _validate(profile)

    if profile.latest_resting_voltage < Decimal("11.80"):
        return BatteryReplacementCycle(MIN_CYCLE_MONTHS, 0, True)
    if profile.latest_resting_voltage < Decimal("12.00") and profile.jump_starts_last_90_days >= 2:
        return BatteryReplacementCycle(MIN_CYCLE_MONTHS, 0, True)

    cycle = BASELINE_CYCLE_MONTHS
    cycle -= _climate_penalty(profile.climate)
    cycle -= _voltage_penalty(
        profile.latest_resting_voltage,
        profile.prior_resting_voltage,
        profile.months_between_voltage_samples,
    )
    cycle -= _maintenance_penalty(profile.corrosion_level, profile.tray_secured)
    cycle += _utilization_adjustment(profile.starts_per_week, profile.climate)
    cycle = _bounded_cycle(cycle)

    if profile.age_months >= cycle:
        return BatteryReplacementCycle(cycle, 0, True)

    remaining = Decimal(cycle - profile.age_months).quantize(Decimal("1"), rounding=ROUND_CEILING)
    return BatteryReplacementCycle(cycle, int(remaining), False)
