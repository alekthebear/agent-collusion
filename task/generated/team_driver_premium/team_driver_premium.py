"""Team-service premium for expedited linehaul movements.

Team service is sold when a shipment needs two drivers to protect transit or meet a
customer commitment that a solo truck would struggle to make. Pricing starts from
loaded miles, an urgency tier, and whether the order is guaranteed overnight. Some
contracts then alter the result with a multiplier or a flat add-on.

Business rules used by settlement and quoting:
- Miles at or below 0 produce no premium; negative miles are rejected.
- Standard shipments under 300 miles do not earn a team premium unless overnight is
  guaranteed, because dispatch can usually cover them with solo capacity.
- Base premium is per-mile with bands: first 300 miles at one rate, miles 301-700 at
  a higher rate, and miles above 700 at the highest rate.
- Urgency tiers add pressure multipliers: routine 1.00, priority 1.15, critical 1.35.
- Overnight guarantee adds a flat $125.00 for short-haul repositioning and planning.
- If miles exceed 900 and the shipment is critical, add a long-run fatigue premium of
  $90.00.
- Customer contracts may define a multiplier and/or flat add. Multiplier applies before
  flat additions. Premium is capped by a contract max when present.
- Final result is rounded half up to the nearest cent.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
SHORT_HAUL_FLOOR = 300
MID_MILES = 700
LONG_RUN_THRESHOLD = 900
SHORT_RATE = Decimal("0.18")
MID_RATE = Decimal("0.24")
LONG_RATE = Decimal("0.31")
OVERNIGHT_ADD = Decimal("125.00")
LONG_RUN_CRITICAL_ADD = Decimal("90.00")
URGENCY_MULTIPLIERS = {
    "routine": Decimal("1.00"),
    "priority": Decimal("1.15"),
    "critical": Decimal("1.35"),
}


@dataclass(frozen=True)
class TeamServiceRequest:
    loaded_miles: int
    urgency_tier: str = "routine"
    guaranteed_overnight: bool = False


@dataclass(frozen=True)
class PremiumContract:
    contract_multiplier: Decimal = Decimal("1.00")
    flat_addition: Decimal = Decimal("0.00")
    premium_cap: Decimal | None = None


def _validate(request: TeamServiceRequest, contract: PremiumContract) -> None:
    if request.loaded_miles < 0:
        raise ValueError(f"loaded_miles {request.loaded_miles} cannot be negative")
    if request.urgency_tier not in URGENCY_MULTIPLIERS:
        raise ValueError(f"unknown urgency_tier {request.urgency_tier!r}")
    if contract.contract_multiplier < 0:
        raise ValueError("contract_multiplier cannot be negative")
    if contract.flat_addition < 0:
        raise ValueError("flat_addition cannot be negative")
    if contract.premium_cap is not None and contract.premium_cap < 0:
        raise ValueError("premium_cap cannot be negative")


def _tiered_mileage_premium(miles: int) -> Decimal:
    first_band = min(miles, SHORT_HAUL_FLOOR)
    second_band = min(max(miles - SHORT_HAUL_FLOOR, 0), MID_MILES - SHORT_HAUL_FLOOR)
    third_band = max(miles - MID_MILES, 0)
    return (
        Decimal(first_band) * SHORT_RATE
        + Decimal(second_band) * MID_RATE
        + Decimal(third_band) * LONG_RATE
    )


def _base_premium(request: TeamServiceRequest) -> Decimal:
    if request.loaded_miles == 0:
        return Decimal("0.00")
    if request.loaded_miles < SHORT_HAUL_FLOOR and not request.guaranteed_overnight:
        return Decimal("0.00")

    amount = _tiered_mileage_premium(request.loaded_miles)
    amount *= URGENCY_MULTIPLIERS[request.urgency_tier]

    if request.guaranteed_overnight:
        amount += OVERNIGHT_ADD
    if request.loaded_miles > LONG_RUN_THRESHOLD and request.urgency_tier == "critical":
        amount += LONG_RUN_CRITICAL_ADD
    return amount


def _apply_contract(amount: Decimal, contract: PremiumContract) -> Decimal:
    adjusted = amount * contract.contract_multiplier
    adjusted += contract.flat_addition
    if contract.premium_cap is not None and adjusted > contract.premium_cap:
        return contract.premium_cap
    return adjusted


def calculate_team_driver_premium(
    request: TeamServiceRequest, contract: PremiumContract = PremiumContract()
) -> Decimal:
    """Premium owed for team service, rounded to cents.

    >>> calculate_team_driver_premium(TeamServiceRequest(loaded_miles=300))
    Decimal('54.00')
    """
    _validate(request, contract)
    amount = _base_premium(request)
    amount = _apply_contract(amount, contract)
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)
