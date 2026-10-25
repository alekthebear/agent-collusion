"""Reconsignment charges when a shipper changes delivery after dispatch.

A reconsignment is billed when the customer changes the destination or stop sequence
after the shipment is already moving. Tidewater's standard rule set is:

- No charge if the instruction is received before dispatch.
- A same-location clerical correction is free when no miles were driven toward the
  original delivery and no stop sequence changes.
- Contract flat-fee customers pay a flat amount per event, with a reduced clerical
  fee for same-city changes made before arrival at the first affected stop.
- Tariff customers pay a base fee plus mileage after a free-mile allowance, rounded
  to the nearest cent with half-up rounding.
- Same-city changes under tariff still owe the base fee, but not mileage.
- If the driver has already arrived at the first affected stop, an after-arrival
  surcharge applies.
- Any added stop beyond the original count adds a per-stop fee, up to a cap of two
  added stops.
- Total charges are capped, and invalid negative values are rejected.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
BASE_FEE = Decimal("85.00")
CLERICAL_FLAT_FEE = Decimal("35.00")
CONTRACT_FLAT_FEE = Decimal("125.00")
AFTER_ARRIVAL_SURCHARGE = Decimal("60.00")
PER_MILE_RATE = Decimal("2.25")
FREE_MILES = 15
ADDED_STOP_FEE = Decimal("40.00")
MAX_ADDED_STOP_BILLABLE = 2
MAX_TOTAL_FEE = Decimal("425.00")


@dataclass(frozen=True)
class ReconsignmentRequest:
    dispatched_at: datetime
    instructed_at: datetime
    arrived_first_affected_stop_at: datetime | None
    miles_already_traveled: Decimal
    original_stop_count: int
    new_stop_count: int
    same_city_change: bool = False
    contract_flat_fee: bool = False


@dataclass(frozen=True)
class ReconsignmentTerms:
    base_fee: Decimal = BASE_FEE
    clerical_flat_fee: Decimal = CLERICAL_FLAT_FEE
    contract_flat_fee_amount: Decimal = CONTRACT_FLAT_FEE
    after_arrival_surcharge: Decimal = AFTER_ARRIVAL_SURCHARGE
    per_mile_rate: Decimal = PER_MILE_RATE
    free_miles: int = FREE_MILES
    added_stop_fee: Decimal = ADDED_STOP_FEE
    max_added_stop_billable: int = MAX_ADDED_STOP_BILLABLE
    max_total_fee: Decimal | None = MAX_TOTAL_FEE


def _validate(request: ReconsignmentRequest, terms: ReconsignmentTerms) -> None:
    if request.miles_already_traveled < 0:
        raise ValueError("miles_already_traveled cannot be negative")
    if request.original_stop_count < 1:
        raise ValueError("original_stop_count must be at least 1")
    if request.new_stop_count < 1:
        raise ValueError("new_stop_count must be at least 1")
    if request.arrived_first_affected_stop_at is not None:
        if request.arrived_first_affected_stop_at < request.dispatched_at:
            raise ValueError("arrival cannot be before dispatch")
    if terms.free_miles < 0 or terms.max_added_stop_billable < 0:
        raise ValueError("term thresholds cannot be negative")


def _added_stop_count(request: ReconsignmentRequest, terms: ReconsignmentTerms) -> int:
    added = max(request.new_stop_count - request.original_stop_count, 0)
    return min(added, terms.max_added_stop_billable)


def _after_arrival(request: ReconsignmentRequest) -> bool:
    return (
        request.arrived_first_affected_stop_at is not None
        and request.instructed_at >= request.arrived_first_affected_stop_at
    )


def _mileage_charge(request: ReconsignmentRequest, terms: ReconsignmentTerms) -> Decimal:
    if request.same_city_change:
        return Decimal("0.00")
    excess = request.miles_already_traveled - Decimal(terms.free_miles)
    if excess <= 0:
        return Decimal("0.00")
    return (excess * terms.per_mile_rate).quantize(CENT, rounding=ROUND_HALF_UP)


def _apply_cap(amount: Decimal, cap: Decimal | None) -> Decimal:
    if cap is not None and amount > cap:
        return cap
    return amount


def calculate_reconsignment_fee(
    request: ReconsignmentRequest, terms: ReconsignmentTerms = ReconsignmentTerms()
) -> Decimal:
    """Reconsignment amount owed for one shipment event.

    Instructions before dispatch are free. A same-location clerical correction is also
    free when made after dispatch if no miles were driven and the stop count is unchanged.
    Otherwise contract customers pay either the clerical fee for a same-city pre-arrival
    change or the contract flat fee. Tariff customers pay the base fee plus mileage past
    the free-mile allowance. Added stops, after-arrival surcharge, and the total cap are
    then applied.
    """
    _validate(request, terms)

    if request.instructed_at <= request.dispatched_at:
        return Decimal("0.00")

    if (
        request.same_city_change
        and request.miles_already_traveled == 0
        and request.new_stop_count == request.original_stop_count
    ):
        return Decimal("0.00")

    if request.contract_flat_fee:
        if request.same_city_change and not _after_arrival(request):
            amount = terms.clerical_flat_fee
        else:
            amount = terms.contract_flat_fee_amount
    else:
        amount = terms.base_fee + _mileage_charge(request, terms)

    if _after_arrival(request):
        amount += terms.after_arrival_surcharge

    amount += Decimal(_added_stop_count(request, terms)) * terms.added_stop_fee
    return _apply_cap(amount.quantize(CENT, rounding=ROUND_HALF_UP), terms.max_total_fee)
