"""Estimate a cargo-claim liability for one shipment incident.

Business rules mirror common truckload cargo terms used in settlements. Liability starts
from the lesser of the shipper's declared cargo value and the proven loss amount. That
base is then limited by any released-value clause, usually expressed as dollars per pound
of affected weight, with a contractual minimum floor for total losses. Recoverable salvage
reduces the exposure after valuation. A customer deductible is then applied, but never
reduces liability below zero.

Special handling is needed for common edge cases. If no damage is proven, liability is
zero. If the shipment is a total loss and the freight is stolen, a salvage estimate is
ignored because there is usually nothing to recover. Hazmat clean-up events add a fixed
administrative reserve when liability remains after deductible. Final amounts are rounded
half up to the nearest cent.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
DEFAULT_RELEASED_RATE = Decimal("0.50")
DEFAULT_TOTAL_LOSS_FLOOR = Decimal("2500.00")
DEFAULT_DEDUCTIBLE = Decimal("500.00")
HAZMAT_ADMIN_RESERVE = Decimal("350.00")
LOW_VALUE_WAIVER_LIMIT = Decimal("1000.00")


@dataclass(frozen=True)
class ClaimFacts:
    declared_value: Decimal
    shipment_weight_lb: Decimal
    damaged_weight_lb: Decimal
    proven_loss_amount: Decimal
    salvage_recovery: Decimal = Decimal("0.00")
    is_total_loss: bool = False
    is_theft: bool = False
    is_hazmat_cleanup: bool = False


@dataclass(frozen=True)
class LiabilityTerms:
    released_value_per_lb: Decimal | None = DEFAULT_RELEASED_RATE
    total_loss_floor: Decimal = DEFAULT_TOTAL_LOSS_FLOOR
    deductible: Decimal = DEFAULT_DEDUCTIBLE


def _validate(facts: ClaimFacts, terms: LiabilityTerms) -> None:
    for name, value in (
        ("declared_value", facts.declared_value),
        ("shipment_weight_lb", facts.shipment_weight_lb),
        ("damaged_weight_lb", facts.damaged_weight_lb),
        ("proven_loss_amount", facts.proven_loss_amount),
        ("salvage_recovery", facts.salvage_recovery),
        ("total_loss_floor", terms.total_loss_floor),
        ("deductible", terms.deductible),
    ):
        if value < 0:
            raise ValueError(f"{name} must be non-negative")
    if terms.released_value_per_lb is not None and terms.released_value_per_lb < 0:
        raise ValueError("released_value_per_lb must be non-negative or None")
    if facts.damaged_weight_lb > facts.shipment_weight_lb:
        raise ValueError("damaged_weight_lb cannot exceed shipment_weight_lb")


def _base_loss(facts: ClaimFacts) -> Decimal:
    if facts.proven_loss_amount == 0 or facts.damaged_weight_lb == 0:
        return Decimal("0.00")
    return min(facts.declared_value, facts.proven_loss_amount)


def _released_value_limit(facts: ClaimFacts, terms: LiabilityTerms) -> Decimal | None:
    if terms.released_value_per_lb is None:
        return None
    affected_weight = facts.shipment_weight_lb if facts.is_total_loss else facts.damaged_weight_lb
    limit = terms.released_value_per_lb * affected_weight
    if facts.is_total_loss and limit < terms.total_loss_floor:
        return terms.total_loss_floor
    return limit


def _salvage_offset(facts: ClaimFacts) -> Decimal:
    if facts.is_total_loss and facts.is_theft:
        return Decimal("0.00")
    return facts.salvage_recovery


def calculate_claim_liability_estimate(
    facts: ClaimFacts, terms: LiabilityTerms = LiabilityTerms()
) -> Decimal:
    """Estimated carrier liability in dollars, rounded to the cent.

    The estimate uses the lesser of declared value and proven loss, applies any
    released-value limit, subtracts salvage, then applies the deductible. Small claims
    at or below 1,000.00 waive the deductible to avoid over-adjusting nuisance claims.
    A hazmat clean-up reserve is added after deductible when any liability remains.
    """
    _validate(facts, terms)
    base = _base_loss(facts)
    if base == 0:
        return Decimal("0.00")

    limit = _released_value_limit(facts, terms)
    valued = min(base, limit) if limit is not None else base
    net = valued - _salvage_offset(facts)
    if net <= 0:
        return Decimal("0.00")

    deductible = Decimal("0.00") if net <= LOW_VALUE_WAIVER_LIMIT else terms.deductible
    liability = net - deductible
    if liability <= 0:
        return Decimal("0.00")
    if facts.is_hazmat_cleanup:
        liability += HAZMAT_ADMIN_RESERVE
    return liability.quantize(CENT, rounding=ROUND_HALF_UP)
