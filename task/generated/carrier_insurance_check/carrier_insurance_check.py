"""Insurance compliance checks for carrier qualification and load tendering.

A carrier can only haul a load when its active insurance coverages satisfy both the
customer's baseline requirements and any stricter requirements created by the load.
Tidewater evaluates three monetary lines here: auto liability, cargo, and trailer
interchange. Expiration dates are inclusive through the listed day.

Business rules:
- Liability is required on every move.
- Cargo is waived for documents-only moves and for loads valued under $2,500.
- Trailer interchange is required only when the carrier uses a customer trailer.
- Refrigerated freight must carry at least $100,000 cargo even when the load value is lower.
- Hazmat requires at least $1,000,000 liability.
- New York City pickups or deliveries require at least $2,000,000 liability.
- The required amount for each line is the greater of the customer's minimum and the
  load-driven minimum, except that a waived cargo requirement stays waived.
- Required amounts are rounded up to the next whole dollar before comparison.
- Available coverage amounts are rounded down to cents. A line passes when active and
  available amount is greater than or equal to the required amount.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, ROUND_DOWN, Decimal

CENT = Decimal("0.01")
WHOLE_DOLLAR = Decimal("1")
NYC_BOROUGHS = {"bronx", "brooklyn", "manhattan", "queens", "staten island"}


@dataclass(frozen=True)
class Coverage:
    limit: Decimal
    expires_on: date


@dataclass(frozen=True)
class CarrierPolicySet:
    liability: Coverage
    cargo: Coverage | None = None
    trailer_interchange: Coverage | None = None


@dataclass(frozen=True)
class InsuranceRequirements:
    minimum_liability: Decimal = Decimal("1000000")
    minimum_cargo: Decimal = Decimal("100000")
    minimum_trailer_interchange: Decimal = Decimal("35000")


@dataclass(frozen=True)
class LoadFacts:
    shipment_value: Decimal
    mode: str = "general"
    uses_customer_trailer: bool = False
    is_hazmat: bool = False
    origin_city: str = ""
    destination_city: str = ""


@dataclass(frozen=True)
class InsuranceCheckResult:
    compliant: bool
    liability_ok: bool
    cargo_ok: bool
    trailer_interchange_ok: bool
    reasons: tuple[str, ...]


def _normalize_money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_DOWN)


def _required_dollars(amount: Decimal) -> Decimal:
    return amount.quantize(WHOLE_DOLLAR, rounding=ROUND_CEILING)


def _is_active(coverage: Coverage | None, on_date: date) -> bool:
    return coverage is not None and coverage.expires_on >= on_date


def _is_nyc(load: LoadFacts) -> bool:
    cities = {load.origin_city.strip().lower(), load.destination_city.strip().lower()}
    return any(city in NYC_BOROUGHS for city in cities)


def _cargo_requirement_waived(load: LoadFacts) -> bool:
    return load.mode == "documents" or load.shipment_value < Decimal("2500")


def _cargo_required(load: LoadFacts) -> Decimal:
    if _cargo_requirement_waived(load):
        return Decimal("0")
    minimum = load.shipment_value
    if load.mode == "refrigerated" and minimum < Decimal("100000"):
        minimum = Decimal("100000")
    return minimum


def evaluate_carrier_insurance_check(
    policies: CarrierPolicySet,
    load: LoadFacts,
    requirements: InsuranceRequirements = InsuranceRequirements(),
    as_of: date | None = None,
) -> InsuranceCheckResult:
    """Return compliance flags and deficiency reasons for one load tender decision."""
    if load.shipment_value < Decimal("0"):
        raise ValueError("shipment_value cannot be negative")
    as_of = as_of or date.today()
    reasons: list[str] = []

    liability_required = requirements.minimum_liability
    if load.is_hazmat and liability_required < Decimal("1000000"):
        liability_required = Decimal("1000000")
    if _is_nyc(load) and liability_required < Decimal("2000000"):
        liability_required = Decimal("2000000")
    liability_required = _required_dollars(liability_required)
    liability_available = _normalize_money(policies.liability.limit)
    liability_ok = _is_active(policies.liability, as_of) and liability_available >= liability_required
    if not liability_ok:
        if not _is_active(policies.liability, as_of):
            reasons.append("liability expired")
        else:
            reasons.append(f"liability below required {liability_required}")

    if _cargo_requirement_waived(load):
        cargo_required = Decimal("0")
        cargo_ok = True
    else:
        cargo_required = _required_dollars(max(requirements.minimum_cargo, _cargo_required(load)))
        cargo = policies.cargo
        cargo_available = _normalize_money(cargo.limit) if cargo is not None else Decimal("0.00")
        cargo_ok = _is_active(cargo, as_of) and cargo_available >= cargo_required
        if not cargo_ok:
            if not _is_active(cargo, as_of):
                reasons.append("cargo missing or expired")
            else:
                reasons.append(f"cargo below required {cargo_required}")

    trailer_required = requirements.minimum_trailer_interchange if load.uses_customer_trailer else Decimal("0")
    trailer_required = _required_dollars(trailer_required)
    if trailer_required == 0:
        trailer_ok = True
    else:
        trailer = policies.trailer_interchange
        trailer_available = _normalize_money(trailer.limit) if trailer is not None else Decimal("0.00")
        trailer_ok = _is_active(trailer, as_of) and trailer_available >= trailer_required
        if not trailer_ok:
            if not _is_active(trailer, as_of):
                reasons.append("trailer interchange missing or expired")
            else:
                reasons.append(f"trailer interchange below required {trailer_required}")

    return InsuranceCheckResult(
        compliant=liability_ok and cargo_ok and trailer_ok,
        liability_ok=liability_ok,
        cargo_ok=cargo_ok,
        trailer_interchange_ok=trailer_ok,
        reasons=tuple(reasons),
    )
