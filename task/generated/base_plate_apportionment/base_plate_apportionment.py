"""Base plate apportionment for IRP-style registration settlement.

Tidewater allocates a truck's annual registration cost across jurisdictions using prior-
year fleet miles and each jurisdiction's published fee schedule. This module computes an
internal settlement amount per jurisdiction for one power unit.

Business rules:
- Only positive miles participate in the allocation. Jurisdictions with zero miles receive
  zero even if they appear on the schedule.
- If total positive miles are below 1,000, the unit is treated as de minimis and no
  apportionment is booked.
- Weight tiers are inclusive upper bounds. The first tier whose ``max_weight_lb`` is at
  least the unit weight supplies the base annual fee.
- A jurisdiction with no matching tier is invalid for the requested weight.
- Percentages are computed from miles to six decimal places using half-up rounding.
- Settlement dollars are the jurisdiction percentage times that jurisdiction's base fee,
  rounded half up to cents.
- Any temporary permit cost is added only when miles in that jurisdiction are below 500,
  because the operation is treated as occasional rather than sustained.
- When a jurisdiction share rounds below $25.00, it is raised to a $25.00 minimum charge
  if that jurisdiction has at least 1,000 miles. The home jurisdiction is exempt from this
  minimum because in-state processing already recovers the administrative floor.
- The home jurisdiction receives a $15.00 credit to reflect in-house processing, but its
  amount cannot go below zero.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
PERCENT_PRECISION = Decimal("0.000001")
MIN_TOTAL_MILES = 1000
OCCASIONAL_MILES = 500
MIN_CHARGE_MILES = 1000
MIN_CHARGE = Decimal("25.00")
HOME_CREDIT = Decimal("15.00")


@dataclass(frozen=True)
class FeeTier:
    max_weight_lb: int
    annual_fee: Decimal


@dataclass(frozen=True)
class JurisdictionSchedule:
    code: str
    tiers: tuple[FeeTier, ...]
    temporary_permit_fee: Decimal = Decimal("0.00")


@dataclass(frozen=True)
class PlateApportionmentInput:
    weight_lb: int
    home_jurisdiction: str
    miles_by_jurisdiction: dict[str, int]
    schedules: tuple[JurisdictionSchedule, ...]


def _positive_miles(miles_by_jurisdiction: dict[str, int]) -> dict[str, int]:
    cleaned: dict[str, int] = {}
    for code, miles in miles_by_jurisdiction.items():
        if miles < 0:
            raise ValueError(f"negative miles for {code}: {miles}")
        if miles > 0:
            cleaned[code] = miles
    return cleaned


def _schedule_map(schedules: tuple[JurisdictionSchedule, ...]) -> dict[str, JurisdictionSchedule]:
    mapped: dict[str, JurisdictionSchedule] = {}
    for schedule in schedules:
        if schedule.code in mapped:
            raise ValueError(f"duplicate schedule for {schedule.code}")
        mapped[schedule.code] = schedule
    return mapped


def _base_fee(weight_lb: int, schedule: JurisdictionSchedule) -> Decimal:
    for tier in sorted(schedule.tiers, key=lambda t: t.max_weight_lb):
        if weight_lb <= tier.max_weight_lb:
            return tier.annual_fee
    raise ValueError(f"no fee tier for {schedule.code} at weight {weight_lb}")


def _share(miles: int, total_miles: int) -> Decimal:
    return (Decimal(miles) / Decimal(total_miles)).quantize(PERCENT_PRECISION, rounding=ROUND_HALF_UP)


def calculate_base_plate_apportionment(data: PlateApportionmentInput) -> dict[str, Decimal]:
    """Allocate annual registration across jurisdictions for one unit.

    Returns a dictionary for every jurisdiction present in ``data.miles_by_jurisdiction``.
    Amounts are rounded to cents.
    """
    if data.weight_lb <= 0:
        raise ValueError(f"weight must be positive: {data.weight_lb}")

    positive_miles = _positive_miles(data.miles_by_jurisdiction)
    result = {code: Decimal("0.00") for code in data.miles_by_jurisdiction}
    total_miles = sum(positive_miles.values())
    if total_miles < MIN_TOTAL_MILES:
        return result

    schedules = _schedule_map(data.schedules)
    for code in positive_miles:
        if code not in schedules:
            raise ValueError(f"missing schedule for {code}")

    for code, miles in positive_miles.items():
        schedule = schedules[code]
        amount = (_share(miles, total_miles) * _base_fee(data.weight_lb, schedule)).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        if miles < OCCASIONAL_MILES:
            amount += schedule.temporary_permit_fee
        if code != data.home_jurisdiction and amount < MIN_CHARGE and miles >= MIN_CHARGE_MILES:
            amount = MIN_CHARGE
        if code == data.home_jurisdiction:
            amount = max(Decimal("0.00"), amount - HOME_CREDIT)
        result[code] = amount.quantize(CENT, rounding=ROUND_HALF_UP)
    return result
