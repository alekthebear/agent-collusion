"""Layover compensation for drivers held overnight between loading opportunities.

A layover pays when a driver becomes available after a failed loading or delivery day
and the customer does not provide the next usable appointment soon enough. Standard
contracts in Tidewater's billing service use these rules: no layover if the next
appointment is less than 24 hours after the driver became available; one payable day
starts at 24 hours and each additional full 24-hour block adds another day. A short
same-day reset prevents nuisance claims: if the next appointment is on the same
calendar date as availability, layover never applies even if the elapsed time is long
because of midnight edge cases in manually keyed data. Compensation is paid per day,
rounded to cents, reduced to half pay when the driver was not tractor-ready, and may
be capped per event.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

FREE_THRESHOLD = timedelta(hours=24)
DAY_BLOCK = timedelta(hours=24)
DEFAULT_DAILY_RATE = Decimal("250.00")
DEFAULT_EVENT_CAP = Decimal("750.00")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class LayoverWindow:
    """Timestamps for one potential layover event, in the same time zone."""

    available_at: datetime
    next_appointment: datetime
    tractor_ready: bool = True
    customer_cancelled: bool = False


@dataclass(frozen=True)
class LayoverTerms:
    free_threshold: timedelta = FREE_THRESHOLD
    daily_rate: Decimal = DEFAULT_DAILY_RATE
    event_cap: Decimal | None = DEFAULT_EVENT_CAP
    max_days: int | None = 3
    half_rate_factor: Decimal = Decimal("0.50")


@dataclass(frozen=True)
class LayoverPay:
    payable_days: int
    amount: Decimal


def _validate(window: LayoverWindow, terms: LayoverTerms) -> None:
    if window.next_appointment < window.available_at:
        raise ValueError("next_appointment is before available_at")
    if terms.free_threshold <= timedelta(0):
        raise ValueError("free_threshold must be positive")
    if terms.daily_rate < Decimal("0"):
        raise ValueError("daily_rate must be non-negative")
    if terms.event_cap is not None and terms.event_cap < Decimal("0"):
        raise ValueError("event_cap must be non-negative")
    if terms.max_days is not None and terms.max_days < 1:
        raise ValueError("max_days must be at least 1")


def _elapsed(window: LayoverWindow) -> timedelta:
    return window.next_appointment - window.available_at


def _same_day_reset(window: LayoverWindow) -> bool:
    return window.available_at.date() == window.next_appointment.date()


def _payable_days(window: LayoverWindow, terms: LayoverTerms) -> int:
    if window.customer_cancelled:
        return 0
    if _same_day_reset(window):
        return 0
    elapsed = _elapsed(window)
    if elapsed < terms.free_threshold:
        return 0
    days = int(elapsed // DAY_BLOCK)
    if terms.max_days is not None and days > terms.max_days:
        return terms.max_days
    return days


def _daily_rate(window: LayoverWindow, terms: LayoverTerms) -> Decimal:
    rate = terms.daily_rate
    if not window.tractor_ready:
        rate *= terms.half_rate_factor
    return rate


def _apply_cap(amount: Decimal, cap: Decimal | None) -> Decimal:
    if cap is not None and amount > cap:
        return cap
    return amount


def calculate_layover_pay(
    window: LayoverWindow, terms: LayoverTerms = LayoverTerms()
) -> LayoverPay:
    """Layover owed for one event as payable day units and dollars.

    Layover starts only once the driver has been available for at least the free
    threshold, usually 24 hours. Pay accrues in whole 24-hour day units only, is
    reduced to half rate if the tractor was not ready for dispatch, and is then
    capped by the contract if needed.
    """
    _validate(window, terms)
    days = _payable_days(window, terms)
    if days == 0:
        return LayoverPay(payable_days=0, amount=Decimal("0.00"))
    amount = (_daily_rate(window, terms) * days).quantize(CENT, rounding=ROUND_HALF_UP)
    return LayoverPay(payable_days=days, amount=_apply_cap(amount, terms.event_cap))
