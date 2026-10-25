"""Tarp accessorial charges for open-deck loads.

Flatbed and step-deck carriers bill tarp pay when a load must be covered in transit.
Billing depends on how many tarps are required, the tarp style, and whether the
commodity needs special protection. The standard rules below are used when a
customer contract or carrier settlement does not override them.

Business rules:
- A tarp charge is billed per tarp actually required.
- Steel tarps are the base style; lumber tarps pay a higher amount because they are
  larger and slower to deploy; smoke tarps pay a lower amount because they cover
  only the nose of the load.
- Weather-sensitive commodities add a surcharge per tarp, except on smoke tarps.
- Machinery loads that require edge protection add a flat handling surcharge once
  per load when at least one full-size tarp is used.
- If the customer marks tarp_included, no tarp fee is billed.
- Carrier settlements may use a different schedule than customer invoices, but both
  use the same rating rules.
- A minimum fee of one tarp applies when tarp_required is true but tarp_count is 0;
  operations uses this when the load confirmation requires tarping but the count was
  omitted.
- More than 8 tarps on one load is treated as invalid input.
- Amounts are rounded to the nearest cent using half-up rounding.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")

BASE_SCHEDULE = {
    "steel": Decimal("75.00"),
    "lumber": Decimal("95.00"),
    "smoke": Decimal("35.00"),
}
WEATHER_SURCHARGE = Decimal("12.50")
EDGE_PROTECTION_SURCHARGE = Decimal("20.00")
EXTRA_TARP_DISCOUNT = Decimal("5.00")
MAX_TARPS = 8


@dataclass(frozen=True)
class TarpLoad:
    tarp_count: int
    tarp_type: str
    commodity: str
    tarp_required: bool = True
    tarp_included: bool = False


@dataclass(frozen=True)
class TarpTerms:
    schedule: dict[str, Decimal] | None = None
    weather_surcharge: Decimal = WEATHER_SURCHARGE
    edge_protection_surcharge: Decimal = EDGE_PROTECTION_SURCHARGE
    extra_tarp_discount: Decimal = EXTRA_TARP_DISCOUNT


def _normalize(text: str) -> str:
    return text.strip().lower()


def _schedule_for(terms: TarpTerms) -> dict[str, Decimal]:
    return BASE_SCHEDULE if terms.schedule is None else terms.schedule


def _validate(load: TarpLoad, terms: TarpTerms) -> None:
    if load.tarp_count < 0:
        raise ValueError("tarp_count cannot be negative")
    if load.tarp_count > MAX_TARPS:
        raise ValueError("tarp_count exceeds maximum supported count")
    tarp_type = _normalize(load.tarp_type)
    if tarp_type not in _schedule_for(terms):
        raise ValueError(f"unsupported tarp_type: {load.tarp_type}")


def _effective_tarp_count(load: TarpLoad) -> int:
    if not load.tarp_required:
        return 0
    return max(1, load.tarp_count)


def _weather_sensitive(commodity: str) -> bool:
    commodity = _normalize(commodity)
    return commodity in {"wallboard", "drywall", "paper", "insulation"}


def _needs_edge_protection(commodity: str) -> bool:
    commodity = _normalize(commodity)
    return commodity in {"machinery", "crated machinery", "metal coils"}


def calculate_tarp_fee(load: TarpLoad, terms: TarpTerms = TarpTerms()) -> Decimal:
    """Return the tarp accessorial for one load.

    The fee uses the schedule rate for the tarp style multiplied by the effective
    tarp count. Loads with more than two tarps receive a small per-tarp discount on
    tarps after the second. Weather-sensitive commodities add a surcharge per tarp
    for full-size tarps only. Machinery-style commodities add one flat surcharge
    when at least one non-smoke tarp is used.
    """
    _validate(load, terms)
    if load.tarp_included:
        return Decimal("0.00")

    count = _effective_tarp_count(load)
    if count == 0:
        return Decimal("0.00")

    tarp_type = _normalize(load.tarp_type)
    rate = _schedule_for(terms)[tarp_type]
    amount = rate * count

    if count > 2:
        amount -= terms.extra_tarp_discount * (count - 2)

    if tarp_type != "smoke" and _weather_sensitive(load.commodity):
        amount += terms.weather_surcharge * count

    if tarp_type != "smoke" and _needs_edge_protection(load.commodity):
        amount += terms.edge_protection_surcharge

    return amount.quantize(CENT, rounding=ROUND_HALF_UP)
