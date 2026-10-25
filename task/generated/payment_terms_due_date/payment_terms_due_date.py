"""Invoice payment terms due dates for carrier settlements and customer billing.

The billing platform uses one rules engine for customer invoices and carrier self-bills.
This module computes the contractual due date from an issue date plus term details.
Standard net terms add calendar days to the issue date. Some contracts use end-of-
month handling: if issued on or after a threshold day, the due date is based on the
last day of the following month instead of simple day addition. After the base date is
chosen, non-business-day rolling applies. Weekend and listed holiday dates can roll
forward to the next business day or backward to the previous business day; a contract
may also specify no rolling. A grace period may then be added in business days.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta


@dataclass(frozen=True)
class PaymentTermsInput:
    issue_date: date
    terms_days: int
    eom_threshold_day: int | None = None
    roll_rule: str = "forward"
    holiday_dates: frozenset[date] = field(default_factory=frozenset)
    grace_business_days: int = 0


_VALID_ROLL_RULES = {"forward", "backward", "none"}


def _validate(terms: PaymentTermsInput) -> None:
    if terms.terms_days < 0:
        raise ValueError("terms_days must be >= 0")
    if terms.grace_business_days < 0:
        raise ValueError("grace_business_days must be >= 0")
    if terms.roll_rule not in _VALID_ROLL_RULES:
        raise ValueError(f"unsupported roll_rule {terms.roll_rule!r}")
    if terms.eom_threshold_day is not None and not 1 <= terms.eom_threshold_day <= 31:
        raise ValueError("eom_threshold_day must be between 1 and 31")


def _last_day_of_month(day: date) -> date:
    if day.month == 12:
        return date(day.year, 12, 31)
    return date(day.year, day.month + 1, 1) - timedelta(days=1)


def _is_business_day(day: date, holidays: frozenset[date]) -> bool:
    return day.weekday() < 5 and day not in holidays


def _roll(day: date, rule: str, holidays: frozenset[date]) -> date:
    if rule == "none" or _is_business_day(day, holidays):
        return day
    step = 1 if rule == "forward" else -1
    current = day
    while not _is_business_day(current, holidays):
        current += timedelta(days=step)
    return current


def _add_business_days(day: date, business_days: int, holidays: frozenset[date]) -> date:
    current = day
    added = 0
    while added < business_days:
        current += timedelta(days=1)
        if _is_business_day(current, holidays):
            added += 1
    return current


def _base_due_date(terms: PaymentTermsInput) -> date:
    if terms.eom_threshold_day is None or terms.issue_date.day < terms.eom_threshold_day:
        return terms.issue_date + timedelta(days=terms.terms_days)

    issue = terms.issue_date
    if issue.month == 12:
        first_of_next_month = date(issue.year + 1, 1, 1)
    else:
        first_of_next_month = date(issue.year, issue.month + 1, 1)
    return _last_day_of_month(first_of_next_month) + timedelta(days=terms.terms_days)


def calculate_payment_terms_due_date(terms: PaymentTermsInput) -> date:
    """Return the contractual due date after EOM logic, rolling, and grace days.

    EOM logic applies only when ``eom_threshold_day`` is set and the issue day is on
    or after the threshold. In that case, the base date is the last day of the next
    month plus ``terms_days``. The base date is then rolled per ``roll_rule`` if it
    lands on a weekend or listed holiday. Finally, ``grace_business_days`` are added
    as business days.

    >>> calculate_payment_terms_due_date(PaymentTermsInput(issue_date=date(2026, 1, 10), terms_days=30))
    datetime.date(2026, 2, 9)
    """
    _validate(terms)
    base = _base_due_date(terms)
    if terms.grace_business_days == 0 and terms.terms_days == 0:
        return base
    rolled = _roll(base, terms.roll_rule, terms.holiday_dates)
    return _add_business_days(rolled, terms.grace_business_days, terms.holiday_dates)
