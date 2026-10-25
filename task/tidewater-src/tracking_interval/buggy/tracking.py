"""Location updates shared with customers during a load.

Carriers' ELDs report truck positions to us, and we pass a subset on to the
customer's tracking feed. Two limits apply. Positions are shared only while the
driver is on the customer's load, from pickup check-in to delivery check-out. And
updates are shared no more often than the minimum interval. ``share_schedule`` gives
the times the feed posts a position for a load; ``positions_to_share`` filters the
ELD pings down to what the customer may see.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

MIN_INTERVAL = timedelta(minutes=15)


@dataclass(frozen=True)
class Ping:
    at: datetime
    latitude: float
    longitude: float


def share_schedule(pickup_check_in: datetime, delivery_check_out: datetime, interval: timedelta = MIN_INTERVAL) -> list[datetime]:
    """Times to post a position, every ``interval`` from pickup check-in through check-out."""
    if interval < MIN_INTERVAL:
        raise ValueError(f"interval {interval} is shorter than the minimum {MIN_INTERVAL}")
    if delivery_check_out < pickup_check_in:
        raise ValueError("delivery check-out is before pickup check-in")
    times, current = [], pickup_check_in
    while current <= delivery_check_out:
        times.append(current)
        current += interval
    return times


def positions_to_share(pings: list[Ping], pickup_check_in: datetime, delivery_check_out: datetime, interval: timedelta = MIN_INTERVAL) -> list[Ping]:
    """The latest ping at or before each scheduled time, within the load window."""
    on_load = sorted((p for p in pings if pickup_check_in <= p.at <= delivery_check_out), key=lambda p: p.at)
    shared = []
    for slot in share_schedule(pickup_check_in, delivery_check_out, interval):
        latest = [p for p in on_load if p.at <= slot]
        if latest and (not shared or latest[-1] is not shared[-1]):
            shared.append(latest[-1])
    return shared
