"""Cargo claim intake: is a loss and damage claim filed in time?

A customer whose freight arrived damaged, short, or not at all files a cargo
claim against the delivery. The claims desk screens each one before an adjuster
looks at it, and ``screen_claim`` is the first check: a claim filed after the
filing window has closed is denied as late. The window runs from the delivery
date (for a load never delivered, from the scheduled delivery date).
"""

import calendar
from dataclasses import dataclass
from datetime import date

FILING_WINDOW_MONTHS = 9
ACCEPTED = "accepted"
DENIED_LATE = "denied_late"


@dataclass(frozen=True)
class Claim:
    claim_id: str
    customer: str
    delivered: date
    filed: date


def _add_months(start: date, months: int) -> date:
    """``start`` moved ``months`` months later, clamped to the end of a short month."""
    month_index = start.month - 1 + months
    year, month = start.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def filing_deadline(delivered: date) -> date:
    """The last day a claim on this delivery can be filed."""
    return _add_months(delivered, FILING_WINDOW_MONTHS)


def screen_claim(claim: Claim) -> str:
    if claim.filed < claim.delivered:
        raise ValueError(f"{claim.claim_id} filed before delivery")
    return ACCEPTED if claim.filed <= filing_deadline(claim.delivered) else DENIED_LATE
