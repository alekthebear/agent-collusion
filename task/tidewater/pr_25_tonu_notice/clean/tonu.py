"""Truck ordered, not used (TONU) fees.

When a customer cancels a load after we have committed a truck to it, the carrier
has usually turned down other freight and may already be driving to the pickup.
The customer then owes a TONU fee. Cancelling with at least the required notice
before the pickup appointment is free; cancelling later than that, or after the
driver has arrived, owes the flat fee. Settlement calls ``tonu_fee`` for every
cancelled load.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

TONU_FEE = Decimal("250.00")
REQUIRED_NOTICE = timedelta(hours=24)


@dataclass(frozen=True)
class CancelledLoad:
    load_id: str
    customer: str
    pickup_appointment: datetime
    cancelled_at: datetime


def notice_given(load: CancelledLoad) -> timedelta:
    """How long before the pickup appointment the customer cancelled (negative if after)."""
    return load.pickup_appointment - load.cancelled_at


def tonu_fee(load: CancelledLoad, fee: Decimal = TONU_FEE) -> Decimal:
    """The TONU fee owed for a cancelled load."""
    if notice_given(load) >= REQUIRED_NOTICE:
        return Decimal("0.00")
    return fee
