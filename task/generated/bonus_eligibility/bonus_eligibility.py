"""Payroll bonus eligibility for linehaul and local fleet employees.

Payroll awards a monthly bonus only when an employee clears all gating rules. The
bonus program balances service quality, safety, equipment use, and attendance:

* Safety is a hard gate. Any preventable accident makes the employee ineligible.
  Two or more moving violations also make the employee ineligible.
* Attendance is also a hard gate. More than one unexcused absence is disqualifying.
  Tardies are tracked in half-day equivalents: every 3 tardies count as 1 absence,
  rounded down for the gate.
* Service and utilization are scored against thresholds by role. Drivers must meet
  both the on-time percentage and miles target for their role.
* Exact threshold values qualify. A protected leave month may waive the service,
  utilization, and attendance gates, but never the safety gate.
* Eligible employees receive a bonus rate applied to gross pay. The final bonus is
  rounded to the nearest cent using half-up rounding. Employees on final warning are
  still eligible, but their computed bonus is reduced by 50%.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


@dataclass(frozen=True)
class BonusMetrics:
    role: str
    gross_pay: Decimal
    on_time_deliveries: int
    total_deliveries: int
    miles: int
    preventable_accidents: int = 0
    moving_violations: int = 0
    unexcused_absences: int = 0
    tardies: int = 0
    protected_leave: bool = False
    final_warning: bool = False


@dataclass(frozen=True)
class BonusRules:
    linehaul_min_on_time: Decimal = Decimal("98.0")
    local_min_on_time: Decimal = Decimal("96.0")
    linehaul_min_miles: int = 9500
    local_min_miles: int = 4200
    max_unexcused_absences: int = 1
    disqualifying_violations: int = 2
    tardies_per_absence: int = 3
    linehaul_bonus_rate: Decimal = Decimal("0.04")
    local_bonus_rate: Decimal = Decimal("0.03")
    warning_multiplier: Decimal = Decimal("0.50")


@dataclass(frozen=True)
class BonusDecision:
    eligible: bool
    amount: Decimal
    reason: str


def _validate(metrics: BonusMetrics, rules: BonusRules) -> None:
    if metrics.role not in {"linehaul", "local"}:
        raise ValueError(f"unsupported role {metrics.role!r}")
    if metrics.gross_pay < 0:
        raise ValueError("gross_pay cannot be negative")
    if metrics.on_time_deliveries < 0 or metrics.total_deliveries < 0:
        raise ValueError("delivery counts cannot be negative")
    if metrics.on_time_deliveries > metrics.total_deliveries:
        raise ValueError("on_time_deliveries cannot exceed total_deliveries")
    if metrics.miles < 0 or metrics.preventable_accidents < 0 or metrics.moving_violations < 0:
        raise ValueError("miles and safety counts cannot be negative")
    if metrics.unexcused_absences < 0 or metrics.tardies < 0:
        raise ValueError("attendance counts cannot be negative")
    if rules.tardies_per_absence <= 0:
        raise ValueError("tardies_per_absence must be positive")


def _on_time_percent(metrics: BonusMetrics) -> Decimal:
    if metrics.total_deliveries == 0:
        return Decimal("100.0")
    return Decimal(metrics.on_time_deliveries) * Decimal("100") / Decimal(metrics.total_deliveries)


def _effective_absences(metrics: BonusMetrics, rules: BonusRules) -> int:
    return metrics.unexcused_absences + (metrics.tardies // rules.tardies_per_absence)


def _role_thresholds(metrics: BonusMetrics, rules: BonusRules) -> tuple[Decimal, int, Decimal]:
    if metrics.role == "linehaul":
        return rules.linehaul_min_on_time, rules.linehaul_min_miles, rules.linehaul_bonus_rate
    return rules.local_min_on_time, rules.local_min_miles, rules.local_bonus_rate


def _bonus_amount(gross_pay: Decimal, rate: Decimal, final_warning: bool, rules: BonusRules) -> Decimal:
    amount = gross_pay * rate
    if final_warning:
        amount *= rules.warning_multiplier
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def evaluate_bonus_eligibility(
    metrics: BonusMetrics, rules: BonusRules = BonusRules()
) -> BonusDecision:
    """Return bonus eligibility and amount for one monthly payroll record.

    Safety gates are checked first. Protected leave bypasses service, utilization,
    and attendance checks, but not accidents or moving violations.
    """
    _validate(metrics, rules)

    if metrics.preventable_accidents > 0:
        return BonusDecision(False, Decimal("0.00"), "preventable accident")
    if metrics.moving_violations >= rules.disqualifying_violations:
        return BonusDecision(False, Decimal("0.00"), "moving violations")

    min_on_time, min_miles, bonus_rate = _role_thresholds(metrics, rules)

    if not metrics.protected_leave:
        if _effective_absences(metrics, rules) > rules.max_unexcused_absences:
            return BonusDecision(False, Decimal("0.00"), "attendance")
        if _on_time_percent(metrics) < min_on_time:
            return BonusDecision(False, Decimal("0.00"), "service")
        if metrics.miles < min_miles:
            return BonusDecision(False, Decimal("0.00"), "utilization")

    amount = _bonus_amount(metrics.gross_pay, bonus_rate, metrics.final_warning, rules)
    return BonusDecision(True, amount, "eligible")
