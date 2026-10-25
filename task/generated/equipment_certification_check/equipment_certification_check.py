"""Equipment certification eligibility for tendering specialized freight.

Some customer loads require certifications or equipment attributes on the assigned
tractor or trailer, such as food-grade cleanliness, liftgate service, or air-ride
suspension. Operations evaluates the assignment against the load's requirement as of
the pickup date. A certification only counts when the type matches, it is effective
on or before pickup, and it has not expired before pickup.

Business rules:
- Requirement matching is case-insensitive and ignores surrounding whitespace.
- Synonyms normalize to the same certification type: ``food grade`` and
  ``food-grade``; ``lift gate`` and ``lift-gate``; ``air ride`` and ``air-ride``.
- A requirement passes when at least one matching equipment certification is active
  on the pickup date.
- ``food-grade`` is stricter: the certification must also have a score of at least
  85.0, rounded to one decimal place with half-up rounding.
- ``liftgate`` requires a score of at least 70.0 when a score is present, but a
  missing score is accepted because many vendors only record the installed option.
- ``air-ride`` has no score threshold.
- A certification with a revoked date on or before pickup is not valid, even if its
  expiration date is later.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

TENTH = Decimal("0.1")
FOOD_GRADE_MIN_SCORE = Decimal("85.0")
LIFTGATE_MIN_SCORE = Decimal("70.0")


@dataclass(frozen=True)
class EquipmentCertification:
    certification_type: str
    effective_date: date
    expiration_date: date | None = None
    revoked_date: date | None = None
    score: Decimal | None = None


@dataclass(frozen=True)
class LoadCertificationRequirement:
    required_type: str
    pickup_date: date


def _normalize_type(value: str) -> str:
    normalized = " ".join(value.strip().lower().replace("-", " ").split())
    aliases = {
        "food grade": "food-grade",
        "lift gate": "liftgate",
        "air ride": "air-ride",
    }
    return aliases.get(normalized, normalized)


def _round_score(score: Decimal | None) -> Decimal | None:
    if score is None:
        return None
    return score.quantize(TENTH, rounding=ROUND_HALF_UP)


def _dates_are_valid(certification: EquipmentCertification, pickup_date: date) -> bool:
    if certification.effective_date > pickup_date:
        return False
    if certification.expiration_date is not None and certification.expiration_date < pickup_date:
        return False
    if certification.revoked_date is not None and certification.revoked_date <= pickup_date:
        return False
    return True


def _score_meets_rule(required_type: str, score: Decimal | None) -> bool:
    rounded = _round_score(score)
    if required_type == "food-grade":
        return rounded is not None and rounded >= FOOD_GRADE_MIN_SCORE
    if required_type == "liftgate":
        return rounded is None or rounded >= LIFTGATE_MIN_SCORE
    return True


def _matches_requirement(
    certification: EquipmentCertification, requirement: LoadCertificationRequirement
) -> bool:
    required_type = _normalize_type(requirement.required_type)
    certification_type = _normalize_type(certification.certification_type)
    if certification_type != required_type:
        return False
    if not _dates_are_valid(certification, requirement.pickup_date):
        return False
    return _score_meets_rule(required_type, certification.score)


def evaluate_equipment_certification_check(
    requirement: LoadCertificationRequirement,
    certifications: list[EquipmentCertification],
) -> bool:
    """Return whether the load's required certification is satisfied at pickup.

    The check passes when any certification in ``certifications`` matches the
    normalized required type and is active on ``requirement.pickup_date`` under the
    business rules above.
    """
    if not requirement.required_type.strip():
        raise ValueError("required_type must not be blank")
    for certification in certifications:
        if _matches_requirement(certification, requirement):
            return True
    return False
