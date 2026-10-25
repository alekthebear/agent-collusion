"""Safety score gate for carrier onboarding and spot-load eligibility.

Business rules mirror Tidewater's brokerage controls for public safety data. The
service evaluates one carrier snapshot at a time and returns pass/fail with the
specific failed criteria. A carrier normally passes only when its DOT safety score
is at or below the configured threshold, it has no active federal intervention,
and its insurance filing is recent enough.

Exception handling is intentionally narrow. A carrier with a score above the
threshold may still pass when the overage is within a small grace band and the
carrier has enough consecutive clean months with no intervention. New entrants
without a published score can pass only during a limited age window and only when
there is no intervention. Scores are rounded to one decimal place using half-up
rounding before comparison because upstream feeds often provide extra precision.
Boundary values are inclusive unless noted otherwise.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

TENTH = Decimal("0.1")


@dataclass(frozen=True)
class CarrierSafetySnapshot:
    dot_score: Decimal | None
    has_active_intervention: bool
    insurance_on_file_date: date
    authority_granted_date: date
    consecutive_clean_months: int = 0
    fatal_crashes_last_24m: int = 0
    out_of_service_rate: Decimal = Decimal("0.0")


@dataclass(frozen=True)
class SafetyGateConfig:
    max_dot_score: Decimal = Decimal("65.0")
    score_grace_band: Decimal = Decimal("2.0")
    required_clean_months_for_grace: int = 6
    max_new_entrant_age_days: int = 180
    insurance_stale_after_days: int = 45
    max_out_of_service_rate: Decimal = Decimal("38.0")
    block_fatal_crash_count: int = 1


@dataclass(frozen=True)
class SafetyGateResult:
    passed: bool
    violations: tuple[str, ...] = field(default_factory=tuple)


def _round_score(score: Decimal) -> Decimal:
    return score.quantize(TENTH, rounding=ROUND_HALF_UP)


def _days_old(as_of: date, event_date: date) -> int:
    return (as_of - event_date).days


def _validate(snapshot: CarrierSafetySnapshot, config: SafetyGateConfig, as_of: date) -> None:
    if snapshot.dot_score is not None and snapshot.dot_score < 0:
        raise ValueError("dot_score cannot be negative")
    if snapshot.consecutive_clean_months < 0:
        raise ValueError("consecutive_clean_months cannot be negative")
    if snapshot.fatal_crashes_last_24m < 0:
        raise ValueError("fatal_crashes_last_24m cannot be negative")
    if snapshot.out_of_service_rate < 0 or snapshot.out_of_service_rate > 100:
        raise ValueError("out_of_service_rate must be between 0 and 100")
    if snapshot.insurance_on_file_date > as_of or snapshot.authority_granted_date > as_of:
        raise ValueError("dates cannot be in the future")


def _insurance_is_stale(snapshot: CarrierSafetySnapshot, config: SafetyGateConfig, as_of: date) -> bool:
    return _days_old(as_of, snapshot.insurance_on_file_date) > config.insurance_stale_after_days


def _new_entrant_allowed(snapshot: CarrierSafetySnapshot, config: SafetyGateConfig, as_of: date) -> bool:
    age_days = _days_old(as_of, snapshot.authority_granted_date)
    return age_days <= config.max_new_entrant_age_days and not snapshot.has_active_intervention


def _score_passes(snapshot: CarrierSafetySnapshot, config: SafetyGateConfig) -> bool:
    if snapshot.dot_score is None:
        return False
    rounded = _round_score(snapshot.dot_score)
    if rounded <= config.max_dot_score:
        return True
    grace_limit = config.max_dot_score + config.score_grace_band
    return rounded <= grace_limit and snapshot.consecutive_clean_months >= config.required_clean_months_for_grace


def evaluate_safety_score_gate(
    snapshot: CarrierSafetySnapshot,
    as_of: date,
    config: SafetyGateConfig = SafetyGateConfig(),
) -> SafetyGateResult:
    """Evaluate carrier safety eligibility and list violated criteria.

    The gate fails for stale insurance, active intervention, blocking crash history,
    excessive out-of-service rate, or unacceptable score status. A missing score is
    acceptable only for qualifying new entrants.
    """
    _validate(snapshot, config, as_of)
    violations: list[str] = []

    if snapshot.has_active_intervention:
        violations.append("active_intervention")
    if _insurance_is_stale(snapshot, config, as_of):
        violations.append("stale_insurance")
    if snapshot.fatal_crashes_last_24m >= config.block_fatal_crash_count:
        violations.append("fatal_crash_history")
    if snapshot.out_of_service_rate > config.max_out_of_service_rate:
        violations.append("out_of_service_rate")

    if snapshot.dot_score is None:
        if not _new_entrant_allowed(snapshot, config, as_of):
            violations.append("missing_score")
    elif not _score_passes(snapshot, config):
        violations.append("dot_score")

    return SafetyGateResult(passed=not violations, violations=tuple(violations))
