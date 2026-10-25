"""Sort-and-segregate charges for mixed-SKU delivery stops.

Some receivers require the driver or lumper crew to split freight by SKU, lot, or
store section before unloading can finish. Tidewater bills this as a sort-and-
segregate accessorial using standard warehouse terms: a flat setup charge for
loads that meet the complexity trigger, plus labor billed in started half hours,
subject to a per-stop minimum. Very small and simple loads are not billed.

Business rules used here:
- No fee at all when SKU count is under 8, pallet count is 2 or less, and there is
  no special handling.
- A stop becomes billable when any trigger is met: at least 8 SKUs, more than 2
  pallets, or special handling required.
- Base labor minutes are 20 setup minutes for any billable stop.
- Add 4 minutes per SKU above 5.
- Add 12 minutes for each pallet above 2.
- Add 18 minutes per fragile line and 10 minutes per hazmat line.
- If more than half the lines are fragile or hazmat, add a 15 minute complexity
  surcharge.
- Bill labor in started 30 minute increments at the hourly rate.
- If a stop is billable but computed labor is less than the contractual minimum,
  charge the minimum instead.
- Customer-owned sort labels waive the 20 minute setup charge.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
DEFAULT_HOURLY_RATE = Decimal("52.00")
DEFAULT_MINIMUM_FEE = Decimal("65.00")
INCREMENT_MINUTES = 30


@dataclass(frozen=True)
class SortSegregateStop:
    sku_count: int
    pallet_count: int
    total_lines: int
    fragile_lines: int = 0
    hazmat_lines: int = 0
    customer_labels_provided: bool = False


@dataclass(frozen=True)
class SortSegregateTerms:
    hourly_rate: Decimal = DEFAULT_HOURLY_RATE
    minimum_fee: Decimal = DEFAULT_MINIMUM_FEE


def _validate(stop: SortSegregateStop) -> None:
    if stop.sku_count < 0 or stop.pallet_count < 0 or stop.total_lines < 0:
        raise ValueError("counts cannot be negative")
    if stop.fragile_lines < 0 or stop.hazmat_lines < 0:
        raise ValueError("line counts cannot be negative")
    if stop.fragile_lines + stop.hazmat_lines > stop.total_lines:
        raise ValueError("special-handling lines exceed total lines")


def _is_billable(stop: SortSegregateStop) -> bool:
    return (
        stop.sku_count >= 8
        or stop.pallet_count > 2
        or (stop.fragile_lines + stop.hazmat_lines) > 0
    )


def _labor_minutes(stop: SortSegregateStop) -> int:
    minutes = 0 if stop.customer_labels_provided else 20
    if stop.sku_count > 5:
        minutes += (stop.sku_count - 5) * 4
    if stop.pallet_count > 2:
        minutes += (stop.pallet_count - 2) * 12
    minutes += stop.fragile_lines * 18
    minutes += stop.hazmat_lines * 10
    special = stop.fragile_lines + stop.hazmat_lines
    if stop.total_lines > 0 and special * 2 > stop.total_lines:
        minutes += 15
    return minutes


def _started_increments(minutes: int) -> int:
    whole, partial = divmod(minutes, INCREMENT_MINUTES)
    return whole + (1 if partial else 0)


def calculate_sort_segregate_fee(
    stop: SortSegregateStop, terms: SortSegregateTerms = SortSegregateTerms()
) -> Decimal:
    """Return the sort-and-segregate fee for one stop.

    The fee is zero for non-billable simple stops. For billable stops, labor minutes
    are converted to started 30-minute increments at ``terms.hourly_rate`` and then
    compared with ``terms.minimum_fee``.
    """
    _validate(stop)
    if not _is_billable(stop):
        return Decimal("0.00")
    increments = _started_increments(_labor_minutes(stop))
    amount = (terms.hourly_rate * Decimal(increments) / 2).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    if amount < terms.minimum_fee:
        return terms.minimum_fee
    return amount
