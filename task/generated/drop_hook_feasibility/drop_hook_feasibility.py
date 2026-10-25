"""Evaluate whether a load can run as drop-and-hook under standard equipment rules.

A drop-and-hook move is feasible only when a trailer can be left behind and another
compatible trailer can be pulled without relying on live loading. Operations uses the
rules below when preplanning outbound loads:

* The shipper must allow dropped empties and the receiver must allow trailer pickup.
* A trailer pool must effectively exist at both ends. For planning, that means on-hand
  trailers plus same-day expected returns, minus reserved units, must meet a minimum
  usable count.
* Refrigerated loads need refrigerated trailers at both ends and extra yard depth,
  because protect-from-temperature freight cannot depend on the last unit in the yard.
* Hazmat loads require hazmat-approved yards at both ends and at least one spare usable
  trailer beyond the normal minimum.
* Very heavy loads are not planned as drop-and-hook when the estimated cargo weight is
  above 44,000 lb, or above 42,500 lb for reefers, because the trailer selected from
  a pool may not have enough payload tolerance.
* Tight appointments reduce confidence. If pickup lead time is under 4 hours, one more
  usable trailer is required at the shipper. If delivery lead time is under 6 hours,
  one more usable trailer is required at the receiver.
* Yard utilization above 92% blocks drop-and-hook. Utilization from 85% through 92%
  is allowed only with one extra usable trailer of cushion at that yard.

The main function returns a decision object with a boolean result, a short reason code,
and the computed usable trailer counts for both yards.
"""

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal

CENT = Decimal("0.01")
MIN_POOL = 2
REEFER_POOL = 3
HIGH_UTILIZATION = Decimal("0.85")
MAX_UTILIZATION = Decimal("0.92")
WEIGHT_LIMIT_DRY = 44000
WEIGHT_LIMIT_REEFER = 42500


@dataclass(frozen=True)
class YardInventory:
    on_hand: int
    expected_returns_today: int = 0
    reserved: int = 0
    capacity: int = 20
    utilization_override: Decimal | None = None
    hazmat_approved: bool = False
    reefer_ready: bool = False


@dataclass(frozen=True)
class EquipmentRules:
    shipper_allows_drop: bool
    receiver_allows_hook: bool
    refrigerated: bool = False
    hazmat: bool = False
    estimated_weight_lb: int = 0
    pickup_lead_hours: Decimal = Decimal("24")
    delivery_lead_hours: Decimal = Decimal("24")


@dataclass(frozen=True)
class FeasibilityDecision:
    feasible: bool
    reason: str
    shipper_usable: int
    receiver_usable: int


def _validate_yard(yard: YardInventory) -> None:
    if min(yard.on_hand, yard.expected_returns_today, yard.reserved) < 0:
        raise ValueError("yard counts cannot be negative")
    if yard.capacity <= 0:
        raise ValueError("yard capacity must be positive")
    if yard.utilization_override is not None and not (Decimal("0") <= yard.utilization_override <= Decimal("1")):
        raise ValueError("utilization override must be between 0 and 1")


def _usable_trailers(yard: YardInventory) -> int:
    return max(0, yard.on_hand + yard.expected_returns_today - yard.reserved)


def _utilization(yard: YardInventory) -> Decimal:
    if yard.utilization_override is not None:
        return yard.utilization_override.quantize(CENT)
    ratio = Decimal(yard.on_hand) / Decimal(yard.capacity)
    return ratio.quantize(CENT, rounding=ROUND_FLOOR)


def _required_pool(rules: EquipmentRules, at_receiver: bool, utilization: Decimal) -> int:
    required = REEFER_POOL if rules.refrigerated else MIN_POOL
    if rules.hazmat:
        required += 1
    lead = rules.delivery_lead_hours if at_receiver else rules.pickup_lead_hours
    tight_limit = Decimal("6") if at_receiver else Decimal("4")
    if lead < tight_limit:
        required += 1
    if HIGH_UTILIZATION <= utilization <= MAX_UTILIZATION:
        required += 1
    return required


def evaluate_drop_hook_feasibility(
    shipper_yard: YardInventory,
    receiver_yard: YardInventory,
    rules: EquipmentRules,
) -> FeasibilityDecision:
    """Return whether the load can be planned as drop-and-hook.

    Counts are evaluated with same-day returns included and reserved units excluded.
    Inventory thresholds are inclusive: meeting the exact required usable count passes.
    """
    _validate_yard(shipper_yard)
    _validate_yard(receiver_yard)

    if not rules.shipper_allows_drop:
        return FeasibilityDecision(False, "shipper_no_drop", 0, 0)
    if not rules.receiver_allows_hook:
        return FeasibilityDecision(False, "receiver_no_hook", 0, 0)

    limit = WEIGHT_LIMIT_REEFER if rules.refrigerated else WEIGHT_LIMIT_DRY
    if rules.estimated_weight_lb > limit:
        return FeasibilityDecision(False, "weight_exceeds_pool_limit", 0, 0)

    shipper_usable = _usable_trailers(shipper_yard)
    receiver_usable = _usable_trailers(receiver_yard)
    shipper_util = _utilization(shipper_yard)
    receiver_util = _utilization(receiver_yard)

    if shipper_util > MAX_UTILIZATION:
        return FeasibilityDecision(False, "shipper_yard_full", shipper_usable, receiver_usable)
    if receiver_util > MAX_UTILIZATION:
        return FeasibilityDecision(False, "receiver_yard_full", shipper_usable, receiver_usable)

    if rules.refrigerated and (not shipper_yard.reefer_ready or not receiver_yard.reefer_ready):
        return FeasibilityDecision(False, "reefer_not_supported", shipper_usable, receiver_usable)
    if rules.hazmat and (not shipper_yard.hazmat_approved or not receiver_yard.hazmat_approved):
        return FeasibilityDecision(False, "hazmat_not_supported", shipper_usable, receiver_usable)

    shipper_required = _required_pool(rules, at_receiver=False, utilization=shipper_util)
    receiver_required = _required_pool(rules, at_receiver=True, utilization=receiver_util)

    if shipper_usable < shipper_required:
        return FeasibilityDecision(False, "shipper_pool_short", shipper_usable, receiver_usable)
    if receiver_usable < receiver_required:
        return FeasibilityDecision(False, "receiver_pool_short", shipper_usable, receiver_usable)

    return FeasibilityDecision(True, "feasible", shipper_usable, receiver_usable)
