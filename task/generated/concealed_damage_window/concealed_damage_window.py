"""Timeliness window for concealed-damage notices after delivery.

Some receivers allow a short period after delivery to report damage that was not visible
at the dock. Claims ops uses these rules to decide whether a notice is timely. The
standard customer rule is five business days from the delivery date, measured through the
end of the last allowed business day. Weekends do not count. A customer may also list
fixed holiday dates that are skipped like weekends.

Special handling reflects common contracts. Food-grade freight is stricter and allows only
three business days. White-glove service adds one business day because receivers often do
room placement before unpacking. If the delivery occurs after a customer's dock-close time,
the count starts from the next calendar day because the receiving day is treated as
administratively closed. Notices submitted on a non-business day are still timely if they
arrive by the deadline timestamp.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

STANDARD_BUSINESS_DAYS = 5
FOOD_GRADE_BUSINESS_DAYS = 3
WHITE_GLOVE_EXTRA_DAYS = 1
DEFAULT_DOCK_CLOSE = time(17, 0)
END_OF_DAY = time(23, 59, 59)


@dataclass(frozen=True)
class DeliveryRecord:
    delivered_at: datetime
    notice_at: datetime
    service_level: str = "standard"


@dataclass(frozen=True)
class CustomerBusinessCalendar:
    allowed_business_days: int = STANDARD_BUSINESS_DAYS
    dock_close_time: time = DEFAULT_DOCK_CLOSE
    holidays: tuple[date, ...] = field(default_factory=tuple)
    saturday_is_business_day: bool = False


def _validate(record: DeliveryRecord, calendar: CustomerBusinessCalendar) -> None:
    if record.notice_at < record.delivered_at:
        raise ValueError("notice_at is before delivered_at")
    if calendar.allowed_business_days < 1:
        raise ValueError("allowed_business_days must be at least 1")
    if record.service_level not in {"standard", "food_grade", "white_glove"}:
        raise ValueError(f"unsupported service_level {record.service_level!r}")


def _is_business_day(day: date, calendar: CustomerBusinessCalendar) -> bool:
    if day in calendar.holidays:
        return False
    weekday = day.weekday()
    if weekday == 6:
        return False
    if weekday == 5 and not calendar.saturday_is_business_day:
        return False
    return True


def _starting_day(delivered_at: datetime, dock_close_time: time) -> date:
    if delivered_at.time() > dock_close_time:
        return delivered_at.date() + timedelta(days=1)
    return delivered_at.date()


def _allowed_business_days(record: DeliveryRecord, calendar: CustomerBusinessCalendar) -> int:
    days = calendar.allowed_business_days
    if record.service_level == "food_grade":
        days = min(days, FOOD_GRADE_BUSINESS_DAYS)
    elif record.service_level == "white_glove":
        days += WHITE_GLOVE_EXTRA_DAYS
    return days


def _deadline_date(start_day: date, business_days: int, calendar: CustomerBusinessCalendar) -> date:
    counted = 0
    current = start_day
    while True:
        if _is_business_day(current, calendar):
            counted += 1
            if counted == business_days:
                return current
        current += timedelta(days=1)


def _deadline_timestamp(record: DeliveryRecord, calendar: CustomerBusinessCalendar) -> datetime:
    start_day = _starting_day(record.delivered_at, calendar.dock_close_time)
    days = _allowed_business_days(record, calendar)
    last_day = _deadline_date(start_day, days, calendar)
    return datetime.combine(last_day, END_OF_DAY)


def calculate_concealed_damage_window(
    record: DeliveryRecord, calendar: CustomerBusinessCalendar = CustomerBusinessCalendar()
) -> tuple[bool, datetime]:
    """Return whether notice was timely and the exact deadline timestamp.

    The deadline runs through 23:59:59 on the last allowed business day after applying
    service-level adjustments, weekend handling, holidays, and after-close deliveries.
    """
    _validate(record, calendar)
    deadline = _deadline_timestamp(record, calendar)
    return record.notice_at <= deadline, deadline
