"""Compute when a trailer's next periodic inspection comes due.

Tidewater uses the earlier of a mileage interval and a calendar interval to decide
when a trailer needs its next shop inspection. The last completed inspection starts
both clocks. A trailer is considered due on the exact due date or due odometer.

Business rules:
- Standard trailers are due every 90 days or 12,000 miles, whichever comes first.
- Refrigerated trailers run harder and are due every 60 days or 10,000 miles.
- Hazmat-spec trailers are due every 45 days or 8,000 miles.
- Trailers based in California use a stricter 75-day calendar limit, but only if it
  is earlier than the equipment type's normal calendar limit.
- If the last inspection was failed, a mandatory reinspection is due in 7 days and a
  500-mile limit also applies; these tighten the normal schedule but never extend it.
- If the trailer has an active roadside defect hold, it is overdue immediately.
- Odometer readings may not go backwards. Exact threshold values count as due.
- Remaining miles are rounded down to a whole mile. Date calculations are whole-day
  based with no time-of-day handling.
"""

from dataclasses import dataclass
from datetime import date, timedelta

STANDARD_DAYS = 90
STANDARD_MILES = 12000
REEFER_DAYS = 60
REEFER_MILES = 10000
HAZMAT_DAYS = 45
HAZMAT_MILES = 8000
CALIFORNIA_DAYS = 75
FAILED_REINSPECTION_DAYS = 7
FAILED_REINSPECTION_MILES = 500


@dataclass(frozen=True)
class TrailerInspectionRecord:
    last_inspection_date: date
    last_inspection_odometer: int
    current_date: date
    current_odometer: int
    equipment_type: str = "standard"
    jurisdiction: str = "other"
    last_result: str = "pass"
    roadside_defect_hold: bool = False


@dataclass(frozen=True)
class InspectionDueStatus:
    due_date: date
    due_odometer: int
    overdue: bool
    overdue_by_days: int
    overdue_by_miles: int
    remaining_days: int
    remaining_miles: int
    reason: str


def _validate(record: TrailerInspectionRecord) -> None:
    if record.current_odometer < record.last_inspection_odometer:
        raise ValueError("current_odometer is before last_inspection_odometer")
    if record.current_date < record.last_inspection_date:
        raise ValueError("current_date is before last_inspection_date")
    if record.equipment_type not in {"standard", "reefer", "hazmat"}:
        raise ValueError("equipment_type must be standard, reefer, or hazmat")
    if record.last_result not in {"pass", "fail"}:
        raise ValueError("last_result must be pass or fail")


def _base_limits(record: TrailerInspectionRecord) -> tuple[int, int, str]:
    if record.equipment_type == "reefer":
        days, miles = REEFER_DAYS, REEFER_MILES
    elif record.equipment_type == "hazmat":
        days, miles = HAZMAT_DAYS, HAZMAT_MILES
    else:
        days, miles = STANDARD_DAYS, STANDARD_MILES
    reason = record.equipment_type
    if record.jurisdiction == "ca" and CALIFORNIA_DAYS < days:
        days = CALIFORNIA_DAYS
        reason += "+ca"
    return days, miles, reason


def _tighten_for_failed_inspection(days: int, miles: int, reason: str, last_result: str) -> tuple[int, int, str]:
    if last_result != "fail":
        return days, miles, reason
    new_days = min(days, FAILED_REINSPECTION_DAYS)
    new_miles = min(miles, FAILED_REINSPECTION_MILES)
    return new_days, new_miles, reason + "+reinspect"


def _date_due(last_date: date, days: int) -> date:
    return last_date + timedelta(days=days)


def _over_by_days(current_date: date, due_date: date) -> int:
    if current_date <= due_date:
        return 0
    return (current_date - due_date).days


def _over_by_miles(current_odometer: int, due_odometer: int) -> int:
    if current_odometer <= due_odometer:
        return 0
    return current_odometer - due_odometer


def calculate_trailer_inspection_due(record: TrailerInspectionRecord) -> InspectionDueStatus:
    """Return the next due point and whether the trailer is overdue.

    The trailer is overdue if a roadside defect hold exists, or if the current date is
    on or after the due date, or if the current odometer is at or above the due
    odometer.
    """
    _validate(record)
    days, miles, reason = _base_limits(record)
    days, miles, reason = _tighten_for_failed_inspection(days, miles, reason, record.last_result)
    due_date = _date_due(record.last_inspection_date, days)
    due_odometer = record.last_inspection_odometer + miles

    overdue_days = _over_by_days(record.current_date, due_date)
    overdue_miles = _over_by_miles(record.current_odometer, due_odometer)
    remaining_days = max(0, (due_date - record.current_date).days)
    remaining_miles = max(0, due_odometer - record.current_odometer)

    threshold_due = record.current_date >= due_date or record.current_odometer >= due_odometer
    overdue = record.roadside_defect_hold or threshold_due
    if record.roadside_defect_hold:
        reason = reason + "+hold"

    return InspectionDueStatus(
        due_date=due_date,
        due_odometer=due_odometer,
        overdue=overdue,
        overdue_by_days=overdue_days,
        overdue_by_miles=overdue_miles,
        remaining_days=remaining_days,
        remaining_miles=remaining_miles,
        reason=reason,
    )
