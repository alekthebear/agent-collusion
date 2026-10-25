"""On-time delivery percentage for the monthly carrier scorecard.

Carrier management sends every contracted carrier a scorecard at month end, and
the on-time number drives tender priority on the Hartline lanes. A delivery is on
time if it lands before the end of the appointment window plus a 15-minute grace
period. Early is on time.

Late deliveries with an excused delay code are not the carrier's fault (the
shipper loaded late, the consignee refused the appointment, or a weather closure)
and are left out of the measurement entirely. Cancelled loads and loads still in
transit are not measured either.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

GRACE = timedelta(minutes=15)
# Delay codes from the EDI 214 feed that excuse a late delivery.
EXCUSED_CODES = frozenset({"CUST", "CONS", "WX"})
DELIVERED = "delivered"
CANCELLED = "cancelled"
IN_TRANSIT = "in_transit"

ON_TIME = "on_time"
LATE = "late"
EXCUSED = "excused"
SKIPPED = "skipped"


@dataclass(frozen=True)
class Delivery:
    load_id: str
    window_end: datetime
    status: str = DELIVERED
    delivered_at: datetime | None = None
    delay_code: str | None = None


def _is_late(delivery: Delivery) -> bool:
    return delivery.delivered_at > delivery.window_end + GRACE


def _classify(delivery: Delivery) -> str:
    if delivery.status != DELIVERED or delivery.delivered_at is None:
        return SKIPPED
    if not _is_late(delivery):
        return ON_TIME
    if delivery.delay_code in EXCUSED_CODES:
        return EXCUSED
    return LATE


def scorecard_counts(deliveries: list[Delivery]) -> dict[str, int]:
    """How many deliveries fall in each scorecard bucket."""
    counts = Counter(_classify(delivery) for delivery in deliveries)
    return {bucket: counts.get(bucket, 0) for bucket in (ON_TIME, LATE, EXCUSED, SKIPPED)}


def on_time_percentage(deliveries: list[Delivery]) -> float | None:
    """The carrier's on-time percentage, rounded to one decimal place.

    Only on-time and unexcused late deliveries are measured. Returns None when
    nothing in the period is measured, so the scorecard can show "n/a" instead of
    a misleading 0%.
    """
    counts = scorecard_counts(deliveries)
    # Every load that actually delivered this period is measured.
    measured = sum(counts.values()) - counts[SKIPPED]
    if measured == 0:
        return None
    return round(100 * counts[ON_TIME] / measured, 1)
