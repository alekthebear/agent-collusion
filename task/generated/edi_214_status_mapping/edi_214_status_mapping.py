"""Canonical status mapping for inbound EDI 214 shipment events.

Tidewater normalizes carrier 214 updates into a smaller set of tracking statuses for
customer visibility and SLA reporting. Mapping starts with the carrier's event code,
then applies business rules from the shipment milestone context. Exception events take
precedence over routine movement. Refused deliveries outrank delivered. Appointment
arrivals only count as "at_delivery" when the stop is the final stop. Distances near a
stop are interpreted with thresholds: 3.0 miles or less counts as on site, more than
3.0 and up to 25.0 miles is near site. Transit events with less than 1 mile of movement
from the prior report are treated as stationary. Distances are rounded half up to one
decimal place before threshold checks so 3.04 becomes 3.0, while 3.05 becomes 3.1.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

TENTH = Decimal("0.1")

_CODE_TABLE = {
    "AF": "departed_pickup",
    "X3": "arrived_pickup",
    "D1": "delivered",
    "X1": "arrived_delivery",
    "NS": "exception",
    "NA": "exception",
    "SD": "in_transit",
    "CP": "in_transit",
}

_EXCEPTION_CODES = {"NS", "NA"}
_REFUSED_CODES = {"RD", "RF"}
_DELAY_CODES = {"NS"}
_MISSED_APPT_CODES = {"NA"}


@dataclass(frozen=True)
class EDI214Event:
    event_code: str
    miles_to_stop: Decimal | None = None
    miles_since_last_event: Decimal | None = None
    stop_sequence: int = 1
    final_stop_sequence: int = 1
    has_exception_note: bool = False
    proof_of_delivery_signed: bool = False
    refused_by_consignee: bool = False


@dataclass(frozen=True)
class StatusResult:
    status: str
    detail: str


def _normalize_code(code: str) -> str:
    return code.strip().upper()


def _round_tenth(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(TENTH, rounding=ROUND_HALF_UP)


def _validate(event: EDI214Event) -> None:
    if event.stop_sequence < 1 or event.final_stop_sequence < 1:
        raise ValueError("stop sequences must be positive")
    if event.stop_sequence > event.final_stop_sequence:
        raise ValueError("stop_sequence cannot exceed final_stop_sequence")
    for name, value in (("miles_to_stop", event.miles_to_stop), ("miles_since_last_event", event.miles_since_last_event)):
        if value is not None and value < 0:
            raise ValueError(f"{name} cannot be negative")


def _is_final_stop(event: EDI214Event) -> bool:
    return event.stop_sequence == event.final_stop_sequence


def _site_band(miles_to_stop: Decimal | None) -> str | None:
    miles = _round_tenth(miles_to_stop)
    if miles is None:
        return None
    if miles <= Decimal("3.0"):
        return "onsite"
    if miles <= Decimal("25.0"):
        return "nearby"
    return "far"


def _movement_status(event: EDI214Event) -> StatusResult:
    moved = _round_tenth(event.miles_since_last_event)
    if moved is not None and moved < Decimal("1.0"):
        return StatusResult("stationary", "transit update with less than 1.0 mile moved")
    band = _site_band(event.miles_to_stop)
    if band == "onsite":
        return StatusResult("at_stop", "transit update rounded to on-site distance")
    if band == "nearby":
        return StatusResult("near_stop", "transit update near scheduled stop")
    return StatusResult("in_transit", "routine transit event")


def map_edi_214_status(event: EDI214Event) -> StatusResult:
    """Map one raw 214 event into a canonical shipment tracking status."""
    _validate(event)
    code = _normalize_code(event.event_code)

    if event.refused_by_consignee or code in _REFUSED_CODES:
        return StatusResult("delivery_refused", "consignee refused shipment")

    if code in _EXCEPTION_CODES or event.has_exception_note:
        if code in _MISSED_APPT_CODES:
            return StatusResult("appointment_missed", "carrier reported missed appointment")
        if code in _DELAY_CODES or event.has_exception_note:
            return StatusResult("delayed", "exception event overrides routine movement")

    base = _CODE_TABLE.get(code)
    if base == "delivered":
        if event.proof_of_delivery_signed:
            return StatusResult("delivered", "signed proof of delivery received")
        return StatusResult("delivered_pending_pod", "delivery reported without signed POD")

    if base == "arrived_delivery":
        band = _site_band(event.miles_to_stop)
        if _is_final_stop(event) and band == "onsite":
            return StatusResult("at_delivery", "final stop arrival confirmed on site")
        if _is_final_stop(event):
            return StatusResult("near_delivery", "final stop arrival reported but not on site")
        return StatusResult("at_stop", "arrival applies to an intermediate stop")

    if base == "arrived_pickup":
        return StatusResult("at_pickup", "carrier arrived at pickup")

    if base == "departed_pickup":
        return StatusResult("departed_pickup", "carrier departed pickup")

    if base == "in_transit":
        return _movement_status(event)

    return _movement_status(event)
