"""Final cargo-claim filing deadlines for delivered freight.

A claim is timely if the written filing date is on or before the last valid calendar
day allowed by the governing limitation period. Tidewater applies these rules for
routine domestic cargo claims:

- Visible loss or damage uses the base filing period measured from delivery.
- Concealed damage has a shorter notice window measured from delivery. If that
  notice window expires before the base filing period, the earlier concealed-damage
  deadline controls.
- Contracts may extend the base filing period but may not shorten it below the
  statutory floor.
- If no contract period is supplied, the statutory period applies.
- A same-day written exception at delivery preserves concealed-damage rights, so the
  concealed notice window is ignored and only the base period applies.
- When both a day-count and year-count limit are present, the earlier resulting date
  controls.
- Deadlines landing on Saturday move to Friday, while Sunday deadlines move to
  Monday. Weekday deadlines are unchanged.
"""

from dataclasses import dataclass
from datetime import date, timedelta

STATUTORY_LIMIT_DAYS = 270
STATUTORY_LIMIT_YEARS = 2
CONCEALED_NOTICE_DAYS = 5


@dataclass(frozen=True)
class DeliveryFacts:
    delivered_on: date
    concealed_damage: bool = False
    noted_at_delivery: bool = False


@dataclass(frozen=True)
class ClaimTerms:
    contract_limit_days: int | None = None
    contract_limit_years: int | None = None
    statutory_limit_days: int = STATUTORY_LIMIT_DAYS
    statutory_limit_years: int = STATUTORY_LIMIT_YEARS
    concealed_notice_days: int = CONCEALED_NOTICE_DAYS


def _validate(facts: DeliveryFacts, terms: ClaimTerms) -> None:
    if terms.statutory_limit_days < 1:
        raise ValueError("statutory_limit_days must be positive")
    if terms.statutory_limit_years < 1:
        raise ValueError("statutory_limit_years must be positive")
    if terms.concealed_notice_days < 1:
        raise ValueError("concealed_notice_days must be positive")
    if terms.contract_limit_days is not None and terms.contract_limit_days < terms.statutory_limit_days:
        raise ValueError("contract_limit_days cannot be shorter than statutory_limit_days")
    if terms.contract_limit_years is not None and terms.contract_limit_years < terms.statutory_limit_years:
        raise ValueError("contract_limit_years cannot be shorter than statutory_limit_years")
    if facts.noted_at_delivery and not facts.concealed_damage:
        raise ValueError("noted_at_delivery applies only to concealed damage handling")


def _add_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, month=2, day=28)


def _move_weekend(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _base_deadline(delivered_on: date, terms: ClaimTerms) -> date:
    day_limit = terms.contract_limit_days
    if day_limit is None:
        day_limit = terms.statutory_limit_days

    year_limit = terms.contract_limit_years
    if year_limit is None:
        year_limit = terms.statutory_limit_years

    by_days = delivered_on + timedelta(days=day_limit)
    by_years = _add_years(delivered_on, year_limit)
    return min(by_days, by_years)


def _concealed_deadline(facts: DeliveryFacts, terms: ClaimTerms) -> date | None:
    if not facts.concealed_damage or facts.noted_at_delivery:
        return None
    return facts.delivered_on + timedelta(days=terms.concealed_notice_days)


def calculate_claim_filing_deadline(
    facts: DeliveryFacts, terms: ClaimTerms = ClaimTerms()
) -> date:
    """Return the final date a cargo claim may be filed.

    The base deadline is the earlier of the applicable day-count limit and year-count
    limit. For concealed damage not noted at delivery, the concealed notice deadline
    may shorten that base deadline. Weekend adjustment is applied after selecting the
    controlling deadline.
    """
    _validate(facts, terms)
    deadline = _base_deadline(facts.delivered_on, terms)
    concealed = _concealed_deadline(facts, terms)
    if concealed is not None and concealed < deadline:
        deadline = concealed
    return _move_weekend(deadline)
