"""Allocate customer chargebacks onto one or more carrier settlements.

Business rules:
- A chargeback may be tied to one or more loads. Each load receives a configured share
  of the event using ``attribution_weight``; weights must be positive and the total must
  not exceed 1.00. The unattributed remainder is not billed to carriers.
- Each load is then reduced by the carrier fault percentage for that load. Fault less
  than 5% is treated as de minimis and allocates nothing. Fault above 100% is invalid.
- Certain events are softened before settlement allocation: ``service_failure`` events
  forgive the first $50.00 after attribution, and ``cargo_claim`` events with salvage
  credit subtract that credit after attribution but before fault is applied.
- A per-load contractual cap may limit the allocated amount. ``critical`` events ignore
  that cap. Events marked ``customer_error`` allocate nothing.
- Amounts are rounded half-up to the cent only at the final per-load result.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
DE_MINIMIS_FAULT = Decimal("0.05")
SERVICE_FAILURE_FORGIVEN = Decimal("50.00")
ONE = Decimal("1.00")


@dataclass(frozen=True)
class LoadShare:
    settlement_id: str
    attribution_weight: Decimal
    fault_percent: Decimal
    cap_amount: Decimal | None = None


@dataclass(frozen=True)
class Chargeback:
    amount: Decimal
    reason: str
    loads: tuple[LoadShare, ...]
    salvage_credit: Decimal = Decimal("0.00")
    customer_error: bool = False
    critical: bool = False


@dataclass(frozen=True)
class Allocation:
    settlement_id: str
    amount: Decimal


def _validate(chargeback: Chargeback) -> None:
    if chargeback.amount < 0:
        raise ValueError("amount cannot be negative")
    if chargeback.salvage_credit < 0:
        raise ValueError("salvage_credit cannot be negative")
    total_weight = Decimal("0.00")
    for load in chargeback.loads:
        if load.attribution_weight <= 0:
            raise ValueError("attribution_weight must be positive")
        if load.fault_percent < 0 or load.fault_percent > ONE:
            raise ValueError("fault_percent must be between 0 and 1")
        if load.cap_amount is not None and load.cap_amount < 0:
            raise ValueError("cap_amount cannot be negative")
        total_weight += load.attribution_weight
    if total_weight > ONE:
        raise ValueError("total attribution_weight cannot exceed 1.00")


def _reason_adjusted_amount(chargeback: Chargeback, weighted_amount: Decimal) -> Decimal:
    amount = weighted_amount
    if chargeback.reason == "service_failure":
        amount -= SERVICE_FAILURE_FORGIVEN
    elif chargeback.reason == "cargo_claim":
        amount -= chargeback.salvage_credit
    if amount < 0:
        return Decimal("0.00")
    return amount


def _apply_fault(amount: Decimal, fault_percent: Decimal) -> Decimal:
    if fault_percent < DE_MINIMIS_FAULT:
        return Decimal("0.00")
    return amount * fault_percent


def _apply_cap(amount: Decimal, load: LoadShare, critical: bool) -> Decimal:
    if critical or load.cap_amount is None:
        return amount
    if amount > load.cap_amount:
        return load.cap_amount
    return amount


def allocate_chargebacks(chargeback: Chargeback) -> tuple[Allocation, ...]:
    """Allocate a chargeback onto settlements with exact per-load amounts.

    The event amount is first split by attribution weight. The per-load share is then
    adjusted for reason-specific relief, multiplied by carrier fault, capped unless the
    event is critical, and rounded half-up to cents.
    """
    _validate(chargeback)
    if chargeback.customer_error or chargeback.amount == 0 or not chargeback.loads:
        return ()

    allocations: list[Allocation] = []
    for load in chargeback.loads:
        weighted = chargeback.amount * load.attribution_weight
        adjusted = _reason_adjusted_amount(chargeback, weighted)
        faulted = _apply_fault(adjusted, load.fault_percent)
        capped = _apply_cap(faulted, load, chargeback.critical)
        rounded = capped.quantize(CENT, rounding=ROUND_HALF_UP)
        if rounded > 0:
            allocations.append(Allocation(settlement_id=load.settlement_id, amount=rounded))
    return tuple(allocations)
