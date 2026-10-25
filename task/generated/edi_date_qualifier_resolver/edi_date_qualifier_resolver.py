"""Resolve canonical shipment milestone dates from EDI date/time qualifiers.

Business rules
- EDI feeds send many date qualifiers for the same shipment event. We normalize them into
  four milestones: pickup, delivery, tender and appointment.
- A qualifier can carry only a date or a full local timestamp. Date-only values are treated
  as local noon so they do not drift backward when converted with a time-zone offset.
- Timestamps are assumed to be in the stop's local time. We convert them to a canonical UTC
  naive datetime by subtracting ``utc_offset_minutes``.
- For each milestone, qualifiers have business precedence. The earliest candidate among the
  highest-precedence group wins.
- Pickup and delivery values can be corrected when they conflict with nearby appointment
  values: if a pickup is more than 12 hours before the appointment, use the appointment; if a
  delivery is more than 18 hours before the appointment, use the appointment.
- Tender dates older than 45 days before pickup are treated as stale planning data and are
  ignored. If pickup exists but no valid tender remains, infer tender as 2 calendar days before
  pickup at 09:00 UTC.
- Delivery cannot be before pickup. If it is within 6 hours before pickup, snap delivery up to
  pickup; if it is more than 6 hours before pickup, reject the record.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

PICKUP_PRECEDENCE = ("X3", "AF", "X6")
DELIVERY_PRECEDENCE = ("D1", "AG", "X1")
TENDER_PRECEDENCE = ("86", "RD")
APPOINTMENT_PRECEDENCE = ("10", "17")
DATE_ONLY_TIME = time(12, 0)


@dataclass(frozen=True)
class EdiQualifierValue:
    qualifier: str
    event_date: date
    event_time: time | None = None
    utc_offset_minutes: int = 0


@dataclass(frozen=True)
class ResolvedMilestones:
    pickup_at: datetime | None
    delivery_at: datetime | None
    tender_at: datetime | None
    appointment_at: datetime | None


def _validate(values: list[EdiQualifierValue]) -> None:
    for value in values:
        if not -720 <= value.utc_offset_minutes <= 840:
            raise ValueError(f"unsupported utc_offset_minutes {value.utc_offset_minutes}")


def _to_utc(value: EdiQualifierValue) -> datetime:
    local_time = value.event_time or DATE_ONLY_TIME
    local_dt = datetime.combine(value.event_date, local_time)
    return local_dt - timedelta(minutes=value.utc_offset_minutes)


def _qualifier_candidates(values: list[EdiQualifierValue], qualifiers: tuple[str, ...]) -> list[datetime]:
    return [_to_utc(v) for v in values if v.qualifier in qualifiers]


def _best_by_precedence(values: list[EdiQualifierValue], precedence: tuple[str, ...]) -> datetime | None:
    for qualifier in precedence:
        candidates = [_to_utc(v) for v in values if v.qualifier == qualifier]
        if candidates:
            return min(candidates)
    return None


def _infer_tender(pickup_at: datetime | None) -> datetime | None:
    if pickup_at is None:
        return None
    inferred_day = (pickup_at - timedelta(days=2)).date()
    return datetime.combine(inferred_day, time(9, 0))


def resolve_edi_date_qualifiers(values: list[EdiQualifierValue]) -> ResolvedMilestones:
    """Return canonical shipment milestone datetimes in naive UTC.

    >>> values = [EdiQualifierValue("X3", date(2026, 5, 1), time(8, 0), -300)]
    >>> resolve_edi_date_qualifiers(values).pickup_at
    datetime.datetime(2026, 5, 1, 13, 0)
    """
    _validate(values)
    appointment_at = _best_by_precedence(values, APPOINTMENT_PRECEDENCE)
    pickup_at = _best_by_precedence(values, PICKUP_PRECEDENCE)
    delivery_at = _best_by_precedence(values, DELIVERY_PRECEDENCE)
    tender_at = _best_by_precedence(values, TENDER_PRECEDENCE)

    if pickup_at and appointment_at and pickup_at < appointment_at - timedelta(hours=12):
        pickup_at = appointment_at
    if delivery_at and appointment_at and delivery_at < appointment_at - timedelta(hours=18):
        delivery_at = appointment_at

    if tender_at and pickup_at and tender_at < pickup_at - timedelta(days=45):
        tender_at = None
    if tender_at is None:
        tender_at = _infer_tender(pickup_at)

    if delivery_at and pickup_at and delivery_at < pickup_at:
        if delivery_at >= pickup_at - timedelta(hours=6):
            delivery_at = pickup_at
        else:
            raise ValueError("delivery is more than 6 hours before pickup")

    return ResolvedMilestones(
        pickup_at=pickup_at,
        delivery_at=delivery_at,
        tender_at=tender_at,
        appointment_at=appointment_at,
    )
