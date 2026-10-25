"""Carrier operating authority age screening for onboarding and load booking.

A carrier's motor authority must usually be old enough before we can onboard the
carrier or tender a load. Tidewater uses a minimum age in whole days measured from
``authority_granted_on`` through ``reference_date``. The grant date counts as day 0,
so an authority granted on April 1 is 30 days old on May 1.

Business rules implemented here:
- Reject impossible dates where the authority grant is after the reference date.
- A revoked carrier always fails.
- If the authority age meets or exceeds the required minimum days, the carrier passes.
- Otherwise, a carrier may pass by waiver only when all waiver conditions are met:
  the rule allows waivers, the authority is at or above the waiver minimum days,
  there are no recent insurance lapses, and the carrier's out-of-service rate is not
  above the configured maximum.
- If a hazmat load is involved, waiver review is stricter: the carrier must have an
  out-of-service rate at or below the hazmat maximum and cannot have any safety alert.
- Boundary values are inclusive: exactly the minimum days or exactly the rate limit
  passes that check.
- Rates are percentages and are rounded half up to two decimals before comparison so
  upstream values like Decimal('4.995') evaluate consistently at 5.00.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
DEFAULT_MINIMUM_AGE_DAYS = 90
DEFAULT_WAIVER_MINIMUM_DAYS = 60
DEFAULT_MAX_OOS_RATE = Decimal("5.00")
DEFAULT_HAZMAT_MAX_OOS_RATE = Decimal("3.00")


@dataclass(frozen=True)
class CarrierAuthorityFacts:
    authority_granted_on: date
    reference_date: date
    out_of_service_rate: Decimal
    insurance_lapse_days_last_12_months: int = 0
    revoked: bool = False
    safety_alert: bool = False
    hazmat_load: bool = False


@dataclass(frozen=True)
class AuthorityAgePolicy:
    minimum_age_days: int = DEFAULT_MINIMUM_AGE_DAYS
    waiver_minimum_days: int = DEFAULT_WAIVER_MINIMUM_DAYS
    allow_waiver: bool = True
    max_out_of_service_rate: Decimal = DEFAULT_MAX_OOS_RATE
    hazmat_max_out_of_service_rate: Decimal = DEFAULT_HAZMAT_MAX_OOS_RATE


@dataclass(frozen=True)
class AuthorityAgeDecision:
    approved: bool
    used_waiver: bool
    authority_age_days: int
    rounded_out_of_service_rate: Decimal
    reason: str


def _validate(facts: CarrierAuthorityFacts, policy: AuthorityAgePolicy) -> None:
    if facts.authority_granted_on > facts.reference_date:
        raise ValueError("authority grant date is after reference date")
    if facts.insurance_lapse_days_last_12_months < 0:
        raise ValueError("insurance lapse days cannot be negative")
    if policy.minimum_age_days < 0 or policy.waiver_minimum_days < 0:
        raise ValueError("policy day thresholds cannot be negative")
    if policy.waiver_minimum_days > policy.minimum_age_days:
        raise ValueError("waiver minimum cannot exceed minimum age")


def _authority_age_days(granted_on: date, reference_date: date) -> int:
    return (reference_date - granted_on).days


def _rounded_rate(rate: Decimal) -> Decimal:
    return rate.quantize(CENT, rounding=ROUND_HALF_UP)


def _rate_limit(facts: CarrierAuthorityFacts, policy: AuthorityAgePolicy) -> Decimal:
    if facts.hazmat_load:
        return policy.hazmat_max_out_of_service_rate
    return policy.max_out_of_service_rate


def evaluate_carrier_authority_age_check(
    facts: CarrierAuthorityFacts,
    policy: AuthorityAgePolicy = AuthorityAgePolicy(),
) -> AuthorityAgeDecision:
    """Evaluate whether a carrier's authority age passes policy.

    Returns an approval decision with the computed authority age in days and whether
    a waiver path was used.
    """
    _validate(facts, policy)
    age_days = _authority_age_days(facts.authority_granted_on, facts.reference_date)
    rounded_rate = _rounded_rate(facts.out_of_service_rate)

    if facts.revoked:
        return AuthorityAgeDecision(False, False, age_days, rounded_rate, "authority_revoked")

    if age_days >= policy.minimum_age_days:
        return AuthorityAgeDecision(True, False, age_days, rounded_rate, "meets_minimum_age")

    if not policy.allow_waiver:
        return AuthorityAgeDecision(False, False, age_days, rounded_rate, "below_minimum_age")

    if age_days < policy.waiver_minimum_days:
        return AuthorityAgeDecision(False, False, age_days, rounded_rate, "below_waiver_minimum")

    if facts.insurance_lapse_days_last_12_months > 0:
        return AuthorityAgeDecision(False, False, age_days, rounded_rate, "recent_insurance_lapse")

    if rounded_rate > _rate_limit(facts, policy):
        return AuthorityAgeDecision(False, False, age_days, rounded_rate, "out_of_service_rate_too_high")

    if facts.hazmat_load and facts.safety_alert:
        return AuthorityAgeDecision(False, False, age_days, rounded_rate, "hazmat_safety_alert")

    return AuthorityAgeDecision(True, True, age_days, rounded_rate, "approved_by_waiver")
