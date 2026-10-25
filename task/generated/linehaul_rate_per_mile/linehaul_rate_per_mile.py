"""Linehaul rate-per-mile for customer rating before FSC and accessorials.

Business rules mirror common truckload contracts used by Tidewater Freight. Rating is
based on paid miles and a contract schedule with breakpoints. The billed result is the
final linehaul rate per mile, not the total linehaul amount.

Rules:
- Miles must be positive.
- The schedule selects a base per-mile rate by paid-mile band.
- Very short freight under 75 miles is operationally expensive and adds a short-haul
  surcharge to the selected base rate.
- Loads at or above 1,000 miles receive a long-haul discount off the selected base rate.
- Hazmat adds a premium per mile, except on loads under 50 miles where the short-haul
  surcharge already covers the operational premium.
- Team service adds a premium per mile on loads over 250 miles; on shorter runs the
  premium is not applied because teams are priced separately outside this routine.
- If the computed total linehaul would fall below the contract minimum charge, the final
  rate per mile is reset so that miles * rate equals the minimum charge.
- The returned rate is rounded to the nearest cent using half-up rounding, and after
  rounding the minimum charge is still protected by rounding the minimum-derived rate up
  to the cent when needed.
"""

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


@dataclass(frozen=True)
class LinehaulRequest:
    paid_miles: int
    hazmat: bool = False
    team_service: bool = False
    overweight_permit: bool = False


@dataclass(frozen=True)
class ContractTerms:
    under_250_rate: Decimal = Decimal("2.45")
    mile_250_to_999_rate: Decimal = Decimal("2.20")
    mile_1000_plus_rate: Decimal = Decimal("2.05")
    short_haul_surcharge: Decimal = Decimal("0.35")
    long_haul_discount: Decimal = Decimal("0.12")
    hazmat_premium: Decimal = Decimal("0.18")
    team_premium: Decimal = Decimal("0.22")
    overweight_premium: Decimal = Decimal("0.10")
    minimum_charge: Decimal = Decimal("325.00")


def _validate(req: LinehaulRequest, terms: ContractTerms) -> None:
    if req.paid_miles <= 0:
        raise ValueError(f"paid_miles must be positive, got {req.paid_miles}")
    if terms.minimum_charge < 0:
        raise ValueError("minimum_charge cannot be negative")


def _base_rate(paid_miles: int, terms: ContractTerms) -> Decimal:
    if paid_miles < 250:
        return terms.under_250_rate
    if paid_miles < 1000:
        return terms.mile_250_to_999_rate
    return terms.mile_1000_plus_rate


def _adjusted_rate(req: LinehaulRequest, terms: ContractTerms) -> Decimal:
    rate = _base_rate(req.paid_miles, terms)
    if req.paid_miles < 75:
        rate += terms.short_haul_surcharge
    if req.paid_miles >= 1000:
        rate -= terms.long_haul_discount
    if req.hazmat and req.paid_miles >= 50:
        rate += terms.hazmat_premium
    if req.team_service and req.paid_miles > 250:
        rate += terms.team_premium
    if req.overweight_permit:
        rate += terms.overweight_premium
    return rate


def _minimum_rate(paid_miles: int, minimum_charge: Decimal) -> Decimal:
    return minimum_charge / Decimal(paid_miles)


def _round_rate(rate: Decimal) -> Decimal:
    return rate.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_linehaul_rate_per_mile(
    req: LinehaulRequest, terms: ContractTerms = ContractTerms()
) -> Decimal:
    """Return the billed linehaul rate per mile in dollars.

    The function applies contractual breakpoints and service premiums to produce a
    provisional rate. If that provisional rate would yield less than the minimum
    charge, the rate is lifted so the minimum is met. The returned rate is a cent
    amount suitable for multiplying by paid miles for billing.
    """
    _validate(req, terms)
    rate = _adjusted_rate(req, terms)
    minimum_rate = _minimum_rate(req.paid_miles, terms.minimum_charge)
    if Decimal(req.paid_miles) * rate < terms.minimum_charge:
        rate = minimum_rate
    rounded = _round_rate(rate)
    if Decimal(req.paid_miles) * rounded < terms.minimum_charge:
        return minimum_rate.quantize(CENT, rounding=ROUND_CEILING)
    return rounded
