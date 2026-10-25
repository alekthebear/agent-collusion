"""Weekend service surcharges for loads requiring Saturday or Sunday handling.

Tidewater bills a weekend service fee when pickup or delivery occurs on a weekend,
but only on shipments whose commitment requires expedited or guaranteed handling.
The fee depends on the weekend day, whether service happened on pickup, delivery, or
both, and any customer or lane specific overrides. Standard rules are:

- Economy freight never pays a weekend service fee.
- Standard freight pays only for Sunday service.
- Expedited and guaranteed freight pay for Saturday and Sunday service.
- If both pickup and delivery are on billable weekend days, both fees apply.
- A same-day weekend pickup and delivery receives a bundled fee instead of adding the
  two stop fees when a bundle is defined for that day.
- Customer schedules override lane schedules; lane schedules override the default.
- The final amount is rounded half up to the cent, with a $250.00 cap per load.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
LOAD_CAP = Decimal("250.00")
BILLABLE_COMMITMENTS = {"standard", "expedited", "guaranteed"}
SATURDAY_ALLOWED = {"expedited", "guaranteed"}

DEFAULT_SCHEDULE = {
    "saturday_pickup": Decimal("35.00"),
    "saturday_delivery": Decimal("45.00"),
    "saturday_both": Decimal("70.00"),
    "sunday_pickup": Decimal("60.00"),
    "sunday_delivery": Decimal("75.00"),
    "sunday_both": Decimal("120.00"),
}


@dataclass(frozen=True)
class FeeSchedule:
    saturday_pickup: Decimal = DEFAULT_SCHEDULE["saturday_pickup"]
    saturday_delivery: Decimal = DEFAULT_SCHEDULE["saturday_delivery"]
    saturday_both: Decimal | None = DEFAULT_SCHEDULE["saturday_both"]
    sunday_pickup: Decimal = DEFAULT_SCHEDULE["sunday_pickup"]
    sunday_delivery: Decimal = DEFAULT_SCHEDULE["sunday_delivery"]
    sunday_both: Decimal | None = DEFAULT_SCHEDULE["sunday_both"]


@dataclass(frozen=True)
class WeekendServiceRequest:
    pickup_date: date
    delivery_date: date
    commitment: str
    lane_schedule: FeeSchedule | None = None
    customer_schedule: FeeSchedule | None = None


def _validate(request: WeekendServiceRequest) -> None:
    if request.delivery_date < request.pickup_date:
        raise ValueError("delivery_date cannot be before pickup_date")
    if request.commitment not in {"economy", "standard", "expedited", "guaranteed"}:
        raise ValueError(f"unsupported commitment: {request.commitment}")


def _is_billable_day(day: date, commitment: str) -> bool:
    weekday = day.weekday()
    if weekday == 5:
        return commitment in SATURDAY_ALLOWED
    if weekday == 6:
        return commitment in BILLABLE_COMMITMENTS
    return False


def _schedule_for(request: WeekendServiceRequest) -> FeeSchedule:
    if request.customer_schedule is not None:
        return request.customer_schedule
    if request.lane_schedule is not None:
        return request.lane_schedule
    return FeeSchedule()


def _single_stop_fee(kind: str, weekday: int, schedule: FeeSchedule) -> Decimal:
    if weekday == 5:
        return schedule.saturday_pickup if kind == "pickup" else schedule.saturday_delivery
    return schedule.sunday_pickup if kind == "pickup" else schedule.sunday_delivery


def _bundled_fee_if_any(pickup_date: date, delivery_date: date, schedule: FeeSchedule) -> Decimal | None:
    if pickup_date != delivery_date:
        return None
    weekday = pickup_date.weekday()
    if weekday == 5:
        return schedule.saturday_both
    if weekday == 6:
        return schedule.sunday_both
    return None


def calculate_weekend_service_fee(request: WeekendServiceRequest) -> Decimal:
    """Return the weekend service surcharge for one load.

    Weekend fees are assessed only for billable weekend days under the load's
    commitment. Customer schedules override lane schedules and defaults. If pickup
    and delivery occur on the same weekend day and that day's bundle fee is defined,
    the bundle replaces separate stop charges. The result is capped at $250.00.
    """
    _validate(request)
    if request.commitment == "economy":
        return Decimal("0.00")

    schedule = _schedule_for(request)
    pickup_billable = _is_billable_day(request.pickup_date, request.commitment)
    delivery_billable = _is_billable_day(request.delivery_date, request.commitment)

    amount = Decimal("0.00")
    if pickup_billable and delivery_billable:
        bundled = _bundled_fee_if_any(request.pickup_date, request.delivery_date, schedule)
        if bundled is not None:
            amount = bundled
        else:
            amount += _single_stop_fee("pickup", request.pickup_date.weekday(), schedule)
            amount += _single_stop_fee("delivery", request.delivery_date.weekday(), schedule)
    elif pickup_billable:
        amount = _single_stop_fee("pickup", request.pickup_date.weekday(), schedule)
    elif delivery_billable:
        amount = _single_stop_fee("delivery", request.delivery_date.weekday(), schedule)

    if amount > LOAD_CAP:
        amount = LOAD_CAP
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)
