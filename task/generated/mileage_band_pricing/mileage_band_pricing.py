"""Mileage band pricing for linehaul charges on contracted truckload lanes.

Tidewater's rating service uses mileage bands instead of a pure per-mile rate on many
regional contracts. A lane is assigned a base tier by mileage, then optional modifiers
adjust the result for difficult freight patterns:

* Mileage is grouped into inclusive bands with a flat charge per band.
* Eastbound freight can carry a directional premium on longer lanes only.
* Loads touching remote regions can add a fixed surcharge, but short-haul local moves do
  not take the remote surcharge even if the region flag is present.
* Very short shuttle freight under 50 miles is billed at a minimum charge.
* A breakpoint discount applies only when mileage is at or above 700 and the pre-discount
  subtotal is at least 1,000.00.
* Hazardous freight adds 12%, rounded to the cent, after any breakpoint discount.
* The final amount is rounded half up to cents and never allowed below the contract
  minimum charge.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
MINIMUM_CHARGE = Decimal("185.00")
REMOTE_SURCHARGE = Decimal("95.00")
EASTBOUND_LONGHAUL_PREMIUM = Decimal("70.00")
BREAKPOINT_DISCOUNT = Decimal("85.00")
HAZMAT_FACTOR = Decimal("0.12")


@dataclass(frozen=True)
class LaneProfile:
    miles: int
    direction: str = "W"
    region: str = "standard"
    hazmat: bool = False


@dataclass(frozen=True)
class PricingTerms:
    minimum_charge: Decimal = MINIMUM_CHARGE
    remote_surcharge: Decimal = REMOTE_SURCHARGE
    eastbound_longhaul_premium: Decimal = EASTBOUND_LONGHAUL_PREMIUM
    breakpoint_discount: Decimal = BREAKPOINT_DISCOUNT


def _validate(profile: LaneProfile) -> None:
    if profile.miles < 0:
        raise ValueError(f"miles {profile.miles} cannot be negative")
    if profile.direction not in {"E", "W"}:
        raise ValueError(f"unsupported direction {profile.direction!r}")
    if profile.region not in {"standard", "remote", "mountain"}:
        raise ValueError(f"unsupported region {profile.region!r}")


def _band_charge(miles: int) -> Decimal:
    if miles < 50:
        return Decimal("160.00")
    if miles <= 149:
        return Decimal("285.00")
    if miles <= 299:
        return Decimal("465.00")
    if miles <= 499:
        return Decimal("690.00")
    if miles <= 699:
        return Decimal("930.00")
    if miles <= 999:
        return Decimal("1185.00")
    return Decimal("1460.00")


def _directional_premium(profile: LaneProfile, terms: PricingTerms) -> Decimal:
    if profile.direction == "E" and profile.miles >= 300:
        return terms.eastbound_longhaul_premium
    return Decimal("0.00")


def _region_surcharge(profile: LaneProfile, terms: PricingTerms) -> Decimal:
    if profile.miles < 100:
        return Decimal("0.00")
    if profile.region == "remote":
        return terms.remote_surcharge
    if profile.region == "mountain":
        return (terms.remote_surcharge / 2).quantize(CENT, rounding=ROUND_HALF_UP)
    return Decimal("0.00")


def _apply_breakpoint_discount(miles: int, subtotal: Decimal, terms: PricingTerms) -> Decimal:
    if miles >= 700 and subtotal >= Decimal("1000.00"):
        return subtotal - terms.breakpoint_discount
    return subtotal


def calculate_mileage_band_pricing(
    profile: LaneProfile, terms: PricingTerms = PricingTerms()
) -> Decimal:
    """Return the contracted linehaul charge in dollars.

    The lane is priced from its mileage band, then directional and region modifiers are
    added. A breakpoint discount may reduce long-haul expensive moves. Hazmat, when
    applicable, is applied after the discount. The final result is rounded to cents and
    floored at the contract minimum.
    """
    _validate(profile)
    subtotal = _band_charge(profile.miles)
    subtotal += _directional_premium(profile, terms)
    subtotal += _region_surcharge(profile, terms)
    subtotal = _apply_breakpoint_discount(profile.miles, subtotal, terms)
    if profile.hazmat:
        subtotal += (subtotal * HAZMAT_FACTOR).quantize(CENT, rounding=ROUND_HALF_UP)
    total = subtotal.quantize(CENT, rounding=ROUND_HALF_UP)
    if total < terms.minimum_charge:
        return terms.minimum_charge
    return total
