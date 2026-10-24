"""Invoice and due dates for delivered loads, in the consignee's local time.

The nightly billing batch invoices every load delivered since the last run. Per
our customer contracts, a load's invoice date is the calendar date of delivery
where it was delivered (the consignee's time zone), not where we are and not UTC.
Due dates follow from the customer's net terms; one that lands on a weekend moves
to the following Monday.

Delivery timestamps come from the ELD/POD feed as aware UTC datetimes. Consignee
time zones are IANA names from the facility record ("America/New_York").
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DEFAULT_TERMS_DAYS = 30


@dataclass(frozen=True)
class Delivery:
    load_id: str
    delivered_at: datetime
    consignee_tz: str
    terms_days: int = DEFAULT_TERMS_DAYS


@dataclass(frozen=True)
class InvoiceDates:
    invoice_date: date
    due_date: date


def _require_aware(moment: datetime, what: str) -> datetime:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(f"{what} must be timezone-aware")
    return moment.astimezone(timezone.utc)


def _zone_offsets(deliveries: list[Delivery], run_at: datetime) -> dict[str, timedelta]:
    """Each consignee zone's UTC offset, resolved once per batch.

    Resolving the zone for every delivery showed up in the batch profile, and a
    nightly run only covers the last day or so of deliveries.
    """
    names = {d.consignee_tz for d in deliveries}
    return {name: run_at.astimezone(ZoneInfo(name)).utcoffset() for name in names}


def _local_delivery_date(delivered_at: datetime, offset: timedelta) -> date:
    """The calendar date at the consignee when the load was delivered."""
    return (delivered_at + offset).date()


def _roll_off_weekend(day: date) -> date:
    # Saturday -> Monday, Sunday -> Monday.
    if day.weekday() >= 5:
        return day + timedelta(days=7 - day.weekday())
    return day


def due_date(invoice_date: date, terms_days: int) -> date:
    if terms_days < 0:
        raise ValueError("terms_days must be non-negative")
    return _roll_off_weekend(invoice_date + timedelta(days=terms_days))


def invoice_dates_for_batch(deliveries: list[Delivery], run_at: datetime) -> dict[str, InvoiceDates]:
    """Invoice and due dates for every load delivered by ``run_at``.

    Loads delivered after ``run_at`` are left for the next run. All timestamps
    must be timezone-aware.
    """
    run_at = _require_aware(run_at, "run_at")
    zones = _zone_offsets(deliveries, run_at)
    dates = {}
    for delivery in deliveries:
        delivered_at = _require_aware(delivery.delivered_at, f"{delivery.load_id} delivered_at")
        if delivered_at > run_at:
            continue
        invoice_date = _local_delivery_date(delivered_at, zones[delivery.consignee_tz])
        dates[delivery.load_id] = InvoiceDates(invoice_date, due_date(invoice_date, delivery.terms_days))
    return dates
