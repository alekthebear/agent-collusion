"""Fuel consumed while a tractor idles during dwell, breaks, and weather holds.

Tidewater estimates idling burn for settlement and sustainability reporting when no
telematics total is available. The engine burn is based on billable idle hours after
contracted grace time, with a minimum one-tenth-hour billing increment. APU-equipped
tractors burn far less fuel when the ambient temperature is moderate enough for the APU
to carry the hotel load. Reefers add a small tractor-side overhead when they run off the
tractor at very low temperatures. Idle fuel is rounded to the nearest hundredth gallon.

Business rules implemented here:
- Negative hours are invalid.
- Up to 0.2 hours of idle is ignored as grace time.
- Past grace, billable time is rounded up to the next 0.1 hour.
- Engine-only tractors burn 0.80 gal/hr in normal weather.
- In severe weather (temperature below 20 F or above 95 F), the main engine burn rate
  increases by 12.5%.
- If the tractor has an APU and temperature is from 35 F through 80 F inclusive, billable
  idle uses the APU rate of 0.25 gal/hr instead of the engine rate.
- A reefer never changes the APU decision, but if it is powered from the tractor and the
  temperature is below 15 F, add 0.10 gal/hr of tractor-side overhead for the billable
  idle time.
- For safety, total estimated idle burn is capped at 30.00 gallons for one event.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

GRACE_HOURS = Decimal("0.2")
BILLING_INCREMENT_HOURS = Decimal("0.1")
ENGINE_BURN_GPH = Decimal("0.80")
APU_BURN_GPH = Decimal("0.25")
SEVERE_WEATHER_MULTIPLIER = Decimal("1.125")
REEFER_TRACTOR_OVERHEAD_GPH = Decimal("0.10")
MAX_EVENT_GALLONS = Decimal("30.00")
HUNDREDTH = Decimal("0.01")


@dataclass(frozen=True)
class IdleEvent:
    """Inputs for one continuous idling event."""

    idle_hours: Decimal
    ambient_temp_f: int
    has_apu: bool = False
    reefer_powered_by_tractor: bool = False


@dataclass(frozen=True)
class BurnRates:
    """Contracted or configured hourly burn rates."""

    engine_gph: Decimal = ENGINE_BURN_GPH
    apu_gph: Decimal = APU_BURN_GPH
    reefer_tractor_overhead_gph: Decimal = REEFER_TRACTOR_OVERHEAD_GPH


def _validate(event: IdleEvent, rates: BurnRates) -> None:
    if event.idle_hours < 0:
        raise ValueError(f"idle_hours {event.idle_hours} cannot be negative")
    if rates.engine_gph <= 0:
        raise ValueError("engine_gph must be positive")
    if rates.apu_gph <= 0:
        raise ValueError("apu_gph must be positive")
    if rates.reefer_tractor_overhead_gph < 0:
        raise ValueError("reefer_tractor_overhead_gph cannot be negative")


def _billable_hours(idle_hours: Decimal) -> Decimal:
    excess = idle_hours - GRACE_HOURS
    if excess <= 0:
        return Decimal("0.0")
    increments = (excess / BILLING_INCREMENT_HOURS).to_integral_value(rounding="ROUND_CEILING")
    return increments * BILLING_INCREMENT_HOURS


def _apu_applies(event: IdleEvent) -> bool:
    return event.has_apu and 35 <= event.ambient_temp_f <= 80


def _engine_rate(event: IdleEvent, rates: BurnRates) -> Decimal:
    rate = rates.engine_gph
    if event.ambient_temp_f < 20 or event.ambient_temp_f > 95:
        rate *= SEVERE_WEATHER_MULTIPLIER
    return rate


def _reefer_overhead_rate(event: IdleEvent, rates: BurnRates) -> Decimal:
    if event.reefer_powered_by_tractor and event.ambient_temp_f < 15:
        return rates.reefer_tractor_overhead_gph
    return Decimal("0.00")


def calculate_idling_fuel_burn(event: IdleEvent, rates: BurnRates = BurnRates()) -> Decimal:
    """Estimated gallons burned during one idling event.

    The first 0.2 hours are free. Remaining time is rounded up to the next tenth hour.
    If an APU is available and the temperature is between 35 F and 80 F inclusive, the
    APU burn rate is used; otherwise the tractor engine burn rate applies, including the
    severe weather uplift outside 20 F to 95 F inclusive. Reefer tractor-power overhead
    is added only below 15 F. The result is rounded half up to the nearest hundredth and
    capped at 30.00 gallons.
    """
    _validate(event, rates)
    billable_hours = _billable_hours(event.idle_hours)
    if billable_hours == 0:
        return Decimal("0.00")

    base_rate = rates.apu_gph if _apu_applies(event) else _engine_rate(event, rates)
    total_rate = base_rate + _reefer_overhead_rate(event, rates)
    gallons = (billable_hours * total_rate).quantize(HUNDREDTH, rounding=ROUND_HALF_UP)
    if gallons > MAX_EVENT_GALLONS:
        return MAX_EVENT_GALLONS
    return gallons
