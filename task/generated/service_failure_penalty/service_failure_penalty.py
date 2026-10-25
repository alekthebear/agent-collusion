"""Contractual penalties for missed appointments and service failures.

Tidewater applies a standard failure schedule when a carrier misses an appointment
or materially fails service on a load. The settlement system calls
``calculate_service_failure_penalty`` once per breach. Penalties are driven by the
breach type, how late the event occurred beyond a contractual grace period, and a
few commercial protections:

* ``late_pickup`` and ``late_delivery`` use minute-based penalties after the grace
  period, billed per started 30-minute block.
* ``truck_order_not_used`` is a flat fee when cancellation occurs too close to the
  appointment, with a reduced fee for enough notice.
* ``missed_appointment`` is a flat fee, but waived when the carrier reschedules and
  arrives within the same day.
* Amounts are capped by the contract and rounded to the nearest cent using normal
  half-up accounting rules.
* Customer-caused failures, force majeure events, and de minimis delays inside the
  grace period do not bill a penalty.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
BLOCK_MINUTES = 30
LATE_GRACE = timedelta(minutes=15)
TONU_NOTICE_THRESHOLD = timedelta(hours=2)


@dataclass(frozen=True)
class ServiceFailure:
    breach_type: str
    appointment: datetime
    event_time: datetime
    customer_at_fault: bool = False
    force_majeure: bool = False
    rescheduled_same_day: bool = False


@dataclass(frozen=True)
class PenaltyTerms:
    late_pickup_base: Decimal = Decimal("150.00")
    late_pickup_per_block: Decimal = Decimal("35.00")
    late_delivery_base: Decimal = Decimal("200.00")
    late_delivery_per_block: Decimal = Decimal("50.00")
    missed_appointment_fee: Decimal = Decimal("250.00")
    tonu_short_notice_fee: Decimal = Decimal("125.00")
    tonu_very_short_notice_fee: Decimal = Decimal("250.00")
    cap: Decimal | None = Decimal("500.00")
    grace_period: timedelta = LATE_GRACE


def _validate(failure: ServiceFailure) -> None:
    valid = {"late_pickup", "late_delivery", "missed_appointment", "truck_order_not_used"}
    if failure.breach_type not in valid:
        raise ValueError(f"unsupported breach_type {failure.breach_type!r}")


def _round_money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _apply_cap(amount: Decimal, cap: Decimal | None) -> Decimal:
    if cap is not None and amount > cap:
        return cap
    return amount


def _started_blocks(duration: timedelta) -> int:
    minutes = duration.total_seconds() / 60
    if minutes <= 0:
        return 0
    whole, partial = divmod(minutes, BLOCK_MINUTES)
    return int(whole) + (1 if partial else 0)


def _late_penalty(delay: timedelta, base: Decimal, per_block: Decimal, grace: timedelta) -> Decimal:
    over = delay - grace
    if over <= timedelta(0):
        return Decimal("0.00")
    blocks = _started_blocks(over)
    return _round_money(base + (per_block * blocks))


def _tonu_penalty(failure: ServiceFailure, terms: PenaltyTerms) -> Decimal:
    notice = failure.appointment - failure.event_time
    if notice >= TONU_NOTICE_THRESHOLD:
        return _round_money(terms.tonu_short_notice_fee)
    if notice >= timedelta(0):
        return _round_money(terms.tonu_very_short_notice_fee)
    return Decimal("0.00")


def calculate_service_failure_penalty(
    failure: ServiceFailure, terms: PenaltyTerms = PenaltyTerms()
) -> Decimal:
    """Return the contractual penalty for one service failure.

    Late pickup and late delivery penalties apply only to delay beyond the grace
    period, using a base fee plus a per-started-30-minute escalation. Missed
    appointments bill a flat fee unless the stop was successfully rescheduled and
    serviced later the same day. Truck order not used bills by cancellation notice:
    two or more hours notice is the reduced fee, less than two hours is the full fee,
    and notice after the appointment does not bill TONU.
    """
    _validate(failure)
    if failure.customer_at_fault or failure.force_majeure:
        return Decimal("0.00")

    if failure.breach_type == "late_pickup":
        delay = failure.event_time - failure.appointment
        amount = _late_penalty(delay, terms.late_pickup_base, terms.late_pickup_per_block, terms.grace_period)
    elif failure.breach_type == "late_delivery":
        delay = failure.event_time - failure.appointment
        amount = _late_penalty(delay, terms.late_delivery_base, terms.late_delivery_per_block, terms.grace_period)
    elif failure.breach_type == "missed_appointment":
        amount = Decimal("0.00") if failure.rescheduled_same_day else _round_money(terms.missed_appointment_fee)
    else:
        amount = _tonu_penalty(failure, terms)

    return _apply_cap(amount, terms.cap)
