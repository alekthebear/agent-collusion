"""After-hours service charges for appointments outside a facility's normal receiving window.

Tidewater bills an after-hours service fee when a customer requests loading or delivery
outside the local facility calendar. The base fee depends on when the appointment falls:
weekday shoulder periods are cheaper than overnight windows, Saturday is a flat premium,
and Sunday or named holidays are the highest premium. A small facility may waive the fee
for short appointments, and refrigerated loads carry an added premium because staffing and
yard support are harder to arrange.

Business rules implemented here:
- Normal business hours are inclusive of the open time and exclusive of the close time.
- No fee applies for appointments fully inside business hours on a non-holiday weekday.
- Appointments on holidays are billed at the holiday base fee regardless of weekday.
- Sunday appointments use the Sunday base fee all day.
- Saturday appointments use the Saturday base fee all day.
- On weekdays outside business hours, appointments within two hours before opening or two
  hours after closing use the shoulder fee; all other times use the overnight fee.
- Facilities with fewer than ``waiver_staff_threshold`` staff waive the fee when the
  appointment duration is at or below ``small_site_waiver_minutes``.
- Refrigerated loads add ``refrigerated_premium`` unless the resulting amount is waived.
- Amounts are rounded to the nearest cent using half-up rounding.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
DEFAULT_OPEN = time(8, 0)
DEFAULT_CLOSE = time(17, 0)


@dataclass(frozen=True)
class FacilityCalendar:
    open_time: time = DEFAULT_OPEN
    close_time: time = DEFAULT_CLOSE
    holiday_dates: frozenset[date] = field(default_factory=frozenset)
    staff_count: int = 8


@dataclass(frozen=True)
class ServiceRequest:
    appointment_start: datetime
    appointment_end: datetime
    refrigerated: bool = False


@dataclass(frozen=True)
class AfterHoursTerms:
    shoulder_fee: Decimal = Decimal("125.00")
    overnight_fee: Decimal = Decimal("225.00")
    saturday_fee: Decimal = Decimal("275.00")
    sunday_fee: Decimal = Decimal("325.00")
    holiday_fee: Decimal = Decimal("350.00")
    refrigerated_premium: Decimal = Decimal("45.00")
    small_site_waiver_minutes: int = 45
    waiver_staff_threshold: int = 5
    shoulder_window_hours: int = 2


def _validate(request: ServiceRequest, calendar: FacilityCalendar, terms: AfterHoursTerms) -> None:
    if request.appointment_end <= request.appointment_start:
        raise ValueError("appointment_end must be after appointment_start")
    if calendar.close_time <= calendar.open_time:
        raise ValueError("close_time must be after open_time")
    if calendar.staff_count < 0:
        raise ValueError("staff_count cannot be negative")
    if terms.small_site_waiver_minutes < 0 or terms.shoulder_window_hours < 0:
        raise ValueError("time thresholds cannot be negative")


def _duration_minutes(request: ServiceRequest) -> int:
    return int((request.appointment_end - request.appointment_start).total_seconds() // 60)


def _inside_business_hours(request: ServiceRequest, calendar: FacilityCalendar) -> bool:
    start_t = request.appointment_start.time()
    end_t = request.appointment_end.time()
    return start_t >= calendar.open_time and end_t <= calendar.close_time


def _weekday_base_fee(start: datetime, calendar: FacilityCalendar, terms: AfterHoursTerms) -> Decimal:
    open_dt = datetime.combine(start.date(), calendar.open_time)
    close_dt = datetime.combine(start.date(), calendar.close_time)
    shoulder = timedelta(hours=terms.shoulder_window_hours)
    if open_dt - shoulder <= start < open_dt:
        return terms.shoulder_fee
    if close_dt <= start <= close_dt + shoulder:
        return terms.shoulder_fee
    return terms.overnight_fee


def _base_fee(request: ServiceRequest, calendar: FacilityCalendar, terms: AfterHoursTerms) -> Decimal:
    day = request.appointment_start.date()
    weekday = request.appointment_start.weekday()
    if day in calendar.holiday_dates:
        return terms.holiday_fee
    if weekday == 6:
        return terms.sunday_fee
    if weekday == 5:
        return terms.saturday_fee
    if _inside_business_hours(request, calendar):
        return Decimal("0.00")
    return _weekday_base_fee(request.appointment_start, calendar, terms)


def _waived(request: ServiceRequest, calendar: FacilityCalendar, terms: AfterHoursTerms) -> bool:
    return (
        calendar.staff_count < terms.waiver_staff_threshold
        and _duration_minutes(request) <= terms.small_site_waiver_minutes
    )


def calculate_after_hours_service_fee(
    request: ServiceRequest,
    calendar: FacilityCalendar = FacilityCalendar(),
    terms: AfterHoursTerms = AfterHoursTerms(),
) -> Decimal:
    """Return the after-hours service fee in dollars.

    The fee is determined from the appointment start relative to the local business
    calendar, then optional refrigerated premium is added, then any small-site waiver
    reduces the final amount to zero.
    """
    _validate(request, calendar, terms)
    if _waived(request, calendar, terms):
        return Decimal("0.00")
    amount = _base_fee(request, calendar, terms)
    if amount == Decimal("0.00"):
        return amount
    if request.refrigerated:
        amount += terms.refrigerated_premium
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)
