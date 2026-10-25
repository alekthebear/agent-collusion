"""Freeze-protection accessorials for temperature-sensitive freight.

Freeze protection covers the added cost of protecting freight from subfreezing weather.
Tidewater bills it only on lanes and dates where exposure is credible and only for
loads that actually need the service. The standard rules are:

* No charge when freeze protection is not requested.
* Reefers include basic protection in the linehaul and are never billed this fee.
* Dry vans and heated trailers may bill when the shipment's protection threshold is
  34 F or higher and the lane is in freeze season.
* Freeze season is November through March for northern lanes and December through
  February for southern lanes.
* Contract pricing may be per trip or per day. Per-day pricing bills by started
  transit day, counting any partial day as a full day.
* Heated trailers carry a higher base amount than dry vans.
* Very temperature-sensitive freight (threshold 38 F or above) adds a premium.
* If the lowest forecast temperature on the trip is above the shipment threshold,
  no freeze fee is billed even in season.
* Extreme cold below 10 F adds a surcharge, but the total fee is capped.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
TRIP_BASE_DRY = Decimal("85.00")
TRIP_BASE_HEATED = Decimal("130.00")
DAY_BASE_DRY = Decimal("45.00")
DAY_BASE_HEATED = Decimal("70.00")
SENSITIVE_PREMIUM = Decimal("20.00")
EXTREME_COLD_SURCHARGE = Decimal("35.00")
MAX_FEE = Decimal("325.00")


@dataclass(frozen=True)
class FreezeProtectionRequest:
    ship_date: date
    transit_days: int
    lowest_forecast_f: int
    threshold_f: int
    region: str
    equipment_type: str
    protection_requested: bool = True


@dataclass(frozen=True)
class FreezeProtectionTerms:
    pricing_mode: str = "trip"
    trip_base_dry: Decimal = TRIP_BASE_DRY
    trip_base_heated: Decimal = TRIP_BASE_HEATED
    day_base_dry: Decimal = DAY_BASE_DRY
    day_base_heated: Decimal = DAY_BASE_HEATED
    sensitive_premium: Decimal = SENSITIVE_PREMIUM
    extreme_cold_surcharge: Decimal = EXTREME_COLD_SURCHARGE
    fee_cap: Decimal = MAX_FEE


def _validate(request: FreezeProtectionRequest, terms: FreezeProtectionTerms) -> None:
    if request.transit_days < 1:
        raise ValueError("transit_days must be at least 1")
    if request.region not in {"north", "south"}:
        raise ValueError(f"unsupported region {request.region!r}")
    if request.equipment_type not in {"dry_van", "heated", "reefer"}:
        raise ValueError(f"unsupported equipment_type {request.equipment_type!r}")
    if terms.pricing_mode not in {"trip", "daily"}:
        raise ValueError(f"unsupported pricing_mode {terms.pricing_mode!r}")


def _in_freeze_season(ship_date: date, region: str) -> bool:
    month = ship_date.month
    if region == "north":
        return month in {11, 12, 1, 2, 3}
    return month in {12, 1, 2}


def _base_rate(request: FreezeProtectionRequest, terms: FreezeProtectionTerms) -> Decimal:
    heated = request.equipment_type == "heated"
    if terms.pricing_mode == "trip":
        return terms.trip_base_heated if heated else terms.trip_base_dry
    daily = terms.day_base_heated if heated else terms.day_base_dry
    return daily * request.transit_days


def _premium(request: FreezeProtectionRequest, terms: FreezeProtectionTerms) -> Decimal:
    return terms.sensitive_premium if request.threshold_f >= 38 else Decimal("0.00")


def _surcharge(request: FreezeProtectionRequest, terms: FreezeProtectionTerms) -> Decimal:
    return terms.extreme_cold_surcharge if request.lowest_forecast_f < 10 else Decimal("0.00")


def calculate_freeze_protection_fee(
    request: FreezeProtectionRequest,
    terms: FreezeProtectionTerms = FreezeProtectionTerms(),
) -> Decimal:
    """Freeze-protection amount for one load, rounded to cents.

    The fee applies only when protection was requested, the equipment does not
    already include it, the lane is in seasonal scope, the shipment threshold is at
    least 34 F, and the forecast reaches or drops below that threshold.
    """
    _validate(request, terms)
    if not request.protection_requested:
        return Decimal("0.00")
    if request.equipment_type == "reefer":
        return Decimal("0.00")
    if request.threshold_f < 34:
        return Decimal("0.00")
    if not _in_freeze_season(request.ship_date, request.region):
        return Decimal("0.00")
    if request.lowest_forecast_f > request.threshold_f:
        return Decimal("0.00")

    amount = _base_rate(request, terms) + _premium(request, terms) + _surcharge(request, terms)
    amount = amount.quantize(CENT, rounding=ROUND_HALF_UP)
    return min(amount, terms.fee_cap)
