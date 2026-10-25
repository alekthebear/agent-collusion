"""CDL medical card due status for dispatch eligibility.

Dispatch can only assign a driver when the driver's medical certification will remain
valid through the operational risk window for the trip. Tidewater uses these rules:

- A card is expired after its expiration date.
- There is a 15-day post-expiration grace window for office follow-up, but a driver in
  grace is still not dispatch-eligible.
- A driver is considered due soon when the card expires within 30 days of the review
  date; however, hazmat-qualified drivers use a tighter 21-day threshold.
- Long-haul planning adds a buffer: if a dispatch horizon is more than 7 days, require
  validity through the horizon plus 2 extra days.
- Drivers on medical variance must renew earlier; subtract 10 days from the applicable
  due-soon threshold, but never below 7 days.
- Return a status, dispatch eligibility, and the next review date that should trigger
  office follow-up. Monetary values are not involved, but dates must be handled at
  exact day boundaries.
"""

from dataclasses import dataclass
from datetime import date, timedelta

GRACE_DAYS = 15
STANDARD_DUE_SOON_DAYS = 30
HAZMAT_DUE_SOON_DAYS = 21
VARIANCE_REDUCTION_DAYS = 10
MIN_DUE_SOON_DAYS = 7
LONG_HAUL_TRIGGER_DAYS = 7
LONG_HAUL_EXTRA_BUFFER_DAYS = 2


@dataclass(frozen=True)
class DriverMedicalRecord:
    expiration_date: date
    review_date: date
    hazmat_qualified: bool = False
    medical_variance: bool = False
    dispatch_horizon_days: int = 0


@dataclass(frozen=True)
class MedicalDueResult:
    status: str
    dispatch_eligible: bool
    days_until_expiration: int
    grace_end_date: date | None
    due_soon_threshold_days: int
    next_review_date: date


def _validate(record: DriverMedicalRecord) -> None:
    if record.dispatch_horizon_days < 0:
        raise ValueError("dispatch_horizon_days cannot be negative")


def _due_soon_threshold(record: DriverMedicalRecord) -> int:
    base = HAZMAT_DUE_SOON_DAYS if record.hazmat_qualified else STANDARD_DUE_SOON_DAYS
    if record.medical_variance:
        base -= VARIANCE_REDUCTION_DAYS
    return max(base, MIN_DUE_SOON_DAYS)


def _required_valid_through(record: DriverMedicalRecord) -> date:
    required = record.review_date + timedelta(days=record.dispatch_horizon_days)
    if record.dispatch_horizon_days > LONG_HAUL_TRIGGER_DAYS:
        required += timedelta(days=LONG_HAUL_EXTRA_BUFFER_DAYS)
    return required


def _status(record: DriverMedicalRecord, days_until_expiration: int, threshold: int) -> str:
    if days_until_expiration < 0:
        if days_until_expiration >= -GRACE_DAYS:
            return "grace"
        return "expired"
    if days_until_expiration <= threshold:
        return "due_soon"
    return "current"


def _next_review_date(record: DriverMedicalRecord, status: str, threshold: int) -> date:
    if status in {"grace", "expired"}:
        return record.review_date
    return record.expiration_date - timedelta(days=threshold)


def calculate_driver_medical_due(record: DriverMedicalRecord) -> MedicalDueResult:
    """Summarize medical-card timing for dispatch and office follow-up.

    The card must be valid through the dispatch horizon measured from ``review_date``.
    When the horizon exceeds 7 days, 2 extra buffer days are required. A card in grace
    remains in follow-up but is not dispatch-eligible.
    """
    _validate(record)
    days_until_expiration = (record.expiration_date - record.review_date).days
    threshold = _due_soon_threshold(record)
    status = _status(record, days_until_expiration, threshold)
    required_valid_through = _required_valid_through(record)
    dispatch_eligible = record.expiration_date >= required_valid_through and days_until_expiration >= 0
    grace_end_date = None
    if days_until_expiration < 0 and days_until_expiration >= -GRACE_DAYS:
        grace_end_date = record.expiration_date + timedelta(days=GRACE_DAYS)
    return MedicalDueResult(
        status=status,
        dispatch_eligible=dispatch_eligible,
        days_until_expiration=days_until_expiration,
        grace_end_date=grace_end_date,
        due_soon_threshold_days=threshold,
        next_review_date=_next_review_date(record, status, threshold),
    )
