"""Driver endorsement compliance for dispatched loads.

A driver's license endorsements must match the freight and equipment on the load.
Dispatch uses these rules before tendering a trip. Hazmat endorsement is required
when placarded hazmat ships, but a cargo tank carrying only residue does not require
hazmat. Tanker endorsement is required for a bulk package of liquids or gases with a
rated capacity over 1,000 gallons, except that an empty non-residue tank does not
require tanker. Doubles endorsement is required whenever the power unit pulls two or
more trailing units. A restricted intrastate hazmat endorsement is not accepted for
loads crossing state lines. Drivers under a safety hold fail the check regardless of
endorsements.

The evaluator returns a decision with a rounded risk score from 0.00 to 1.00. Missing
required endorsements add weighted risk, cross-state restricted hazmat adds extra risk,
and a current TWIC card slightly lowers risk for port hazmat loads when the driver
otherwise qualifies.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


@dataclass(frozen=True)
class DriverEndorsements:
    hazmat: bool = False
    tanker: bool = False
    doubles: bool = False
    hazmat_restricted_intrastate: bool = False
    twic: bool = False
    safety_hold: bool = False


@dataclass(frozen=True)
class LoadRequirements:
    placarded_hazmat: bool = False
    crosses_state_lines: bool = False
    is_port_pickup: bool = False
    liquid_or_gas_bulk: bool = False
    tank_capacity_gallons: int = 0
    empty_tank: bool = False
    residue_only: bool = False
    trailing_units: int = 1


@dataclass(frozen=True)
class EndorsementCheckResult:
    approved: bool
    requires_hazmat: bool
    requires_tanker: bool
    requires_doubles: bool
    risk_score: Decimal
    reason: str


def _validate(load: LoadRequirements) -> None:
    if load.tank_capacity_gallons < 0:
        raise ValueError("tank_capacity_gallons cannot be negative")
    if load.trailing_units < 1:
        raise ValueError("trailing_units must be at least 1")
    if load.residue_only and not load.empty_tank:
        raise ValueError("residue_only loads must be marked empty_tank")


def _requires_hazmat(load: LoadRequirements) -> bool:
    if not load.placarded_hazmat:
        return False
    if load.empty_tank and load.residue_only:
        return False
    return True


def _requires_tanker(load: LoadRequirements) -> bool:
    if not load.liquid_or_gas_bulk:
        return False
    if load.empty_tank and not load.residue_only:
        return False
    return load.tank_capacity_gallons > 1000


def _requires_doubles(load: LoadRequirements) -> bool:
    return load.trailing_units >= 2


def _risk_score(driver: DriverEndorsements, load: LoadRequirements, requires_hazmat: bool, requires_tanker: bool, requires_doubles: bool) -> Decimal:
    score = Decimal("0.00")
    if driver.safety_hold:
        score += Decimal("1.00")
    if requires_hazmat and not driver.hazmat:
        score += Decimal("0.55")
    if requires_tanker and not driver.tanker:
        score += Decimal("0.30")
    if requires_doubles and not driver.doubles:
        score += Decimal("0.25")
    if requires_hazmat and driver.hazmat_restricted_intrastate and load.crosses_state_lines:
        score += Decimal("0.20")
    if requires_hazmat and load.is_port_pickup and driver.twic and score == Decimal("0.00"):
        score -= Decimal("0.05")
    if score < Decimal("0.00"):
        score = Decimal("0.00")
    if score > Decimal("1.00"):
        score = Decimal("1.00")
    return score.quantize(CENT, rounding=ROUND_HALF_UP)


def evaluate_driver_endorsement_check(
    driver: DriverEndorsements,
    load: LoadRequirements,
) -> EndorsementCheckResult:
    """Evaluate whether the driver's endorsements satisfy the load requirements."""
    _validate(load)
    requires_hazmat = _requires_hazmat(load)
    requires_tanker = _requires_tanker(load)
    requires_doubles = _requires_doubles(load)

    reasons: list[str] = []
    approved = True

    if driver.safety_hold:
        approved = False
        reasons.append("driver on safety hold")
    if requires_hazmat and not driver.hazmat:
        approved = False
        reasons.append("missing hazmat endorsement")
    if requires_tanker and not driver.tanker:
        approved = False
        reasons.append("missing tanker endorsement")
    if requires_doubles and not driver.doubles:
        approved = False
        reasons.append("missing doubles endorsement")
    if requires_hazmat and driver.hazmat_restricted_intrastate and load.crosses_state_lines:
        approved = False
        reasons.append("restricted hazmat not valid interstate")

    if not reasons:
        reasons.append("meets endorsement requirements")

    return EndorsementCheckResult(
        approved=approved,
        requires_hazmat=requires_hazmat,
        requires_tanker=requires_tanker,
        requires_doubles=requires_doubles,
        risk_score=_risk_score(driver, load, requires_hazmat, requires_tanker, requires_doubles),
        reason="; ".join(reasons),
    )
