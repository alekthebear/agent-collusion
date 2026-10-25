"""Allocate cargo claim liability across involved parties under Tidewater's standard rules.

A settled claim may be spread across line items, packages, or participating carriers.
This module allocates one total claim amount pro rata from each party's contribution
basis, then applies practical settlement rules used by claims:

* negative claim amounts and negative bases are rejected;
* a zero total claim allocates zero to every party;
* parties marked ``excluded`` receive nothing and do not share in the basis;
* if the eligible basis total is zero, the full claim goes to the first eligible party;
* each eligible party may have a contractual minimum participation floor;
* a party with ``fault_percent`` pays at least that percent of the total claim;
* no party can pay more than its package ``declared_value_cap`` when a cap is present;
* allocations are rounded to cents with half-up rounding;
* contractual floors raise a party above its pure pro rata share but do not increase the
  total claim; the remaining claim is spread across the other eligible parties;
* after floors and caps, any remainder is distributed by largest fractional remainder
  among parties that still have room under their caps; if no one has room, the shortfall
  is assigned to the last eligible uncapped party, otherwise an error is raised.
"""

from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class ClaimShare:
    name: str
    basis: Decimal
    fault_percent: Decimal = Decimal("0")
    minimum_amount: Decimal = Decimal("0.00")
    declared_value_cap: Decimal | None = None
    excluded: bool = False


@dataclass(frozen=True)
class Allocation:
    name: str
    amount: Decimal


def _q(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate(total_claim: Decimal, shares: list[ClaimShare]) -> None:
    if total_claim < 0:
        raise ValueError("total_claim cannot be negative")
    if not shares:
        raise ValueError("at least one share is required")
    for share in shares:
        if share.basis < 0 or share.fault_percent < 0 or share.minimum_amount < 0:
            raise ValueError("basis, fault_percent, and minimum_amount cannot be negative")
        if share.fault_percent > HUNDRED:
            raise ValueError("fault_percent cannot exceed 100")
        if share.declared_value_cap is not None and share.declared_value_cap < 0:
            raise ValueError("declared_value_cap cannot be negative")


def _eligible(shares: list[ClaimShare]) -> list[ClaimShare]:
    return [s for s in shares if not s.excluded]


def _floor_for(share: ClaimShare, total_claim: Decimal) -> Decimal:
    fault_floor = total_claim * share.fault_percent / HUNDRED
    floor = max(share.minimum_amount, fault_floor)
    if share.declared_value_cap is not None and floor > share.declared_value_cap:
        raise ValueError(f"floors exceed cap for {share.name}")
    return _q(floor)


def allocate_claim_pro_rata(total_claim: Decimal, shares: list[ClaimShare]) -> list[Allocation]:
    """Allocate a claim amount to parties in cents.

    The result preserves input order and includes excluded parties with zero amounts.
    """
    _validate(total_claim, shares)
    if total_claim == 0:
        return [Allocation(s.name, Decimal("0.00")) for s in shares]

    eligible = _eligible(shares)
    if not eligible:
        raise ValueError("no eligible shares")

    amounts = {s.name: Decimal("0.00") for s in shares}

    if sum(s.basis for s in eligible) == 0:
        first = eligible[0]
        cap = first.declared_value_cap
        if cap is not None and total_claim > cap:
            raise ValueError("claim exceeds available cap")
        amounts[first.name] = _q(total_claim)
        return [Allocation(s.name, amounts[s.name]) for s in shares]

    floors = {s.name: _floor_for(s, total_claim) if not s.excluded else Decimal("0.00") for s in shares}
    floor_total = sum(floors[s.name] for s in eligible)
    if floor_total > total_claim:
        raise ValueError("minimum allocations exceed total claim")

    fixed = [s for s in eligible if floors[s.name] > Decimal("0.00")]
    variable = [s for s in eligible if floors[s.name] == Decimal("0.00")]

    for s in fixed:
        amounts[s.name] = floors[s.name]

    remaining_claim = total_claim - sum(amounts[s.name] for s in eligible)
    if remaining_claim < 0:
        raise ValueError("minimum allocations exceed total claim")

    if remaining_claim == 0 or not variable:
        return [Allocation(s.name, amounts[s.name]) for s in shares]

    basis_total = sum(s.basis for s in variable)
    raw = {}
    if basis_total == 0:
        raw[variable[0].name] = remaining_claim
        for s in variable[1:]:
            raw[s.name] = Decimal("0.00")
    else:
        for s in variable:
            raw[s.name] = remaining_claim * s.basis / basis_total

    for s in variable:
        if s.declared_value_cap is not None and raw[s.name] > s.declared_value_cap:
            raw[s.name] = s.declared_value_cap

    down = {name: amount.quantize(CENT, rounding=ROUND_DOWN) for name, amount in raw.items()}
    allocated = sum(amounts[s.name] for s in fixed) + sum(down.values())
    remainder_cents = int((total_claim - allocated) / CENT)

    ranked = sorted(
        variable,
        key=lambda s: (raw[s.name] - down[s.name], s.basis, s.name),
        reverse=True,
    )
    while remainder_cents > 0:
        moved = False
        for s in ranked:
            cap = s.declared_value_cap
            if cap is not None and down[s.name] + CENT > cap:
                continue
            down[s.name] += CENT
            remainder_cents -= 1
            moved = True
            if remainder_cents == 0:
                break
        if not moved:
            uncapped = [s for s in variable if s.declared_value_cap is None]
            if not uncapped:
                raise ValueError("claim exceeds available caps")
            down[uncapped[-1].name] += CENT * remainder_cents
            remainder_cents = 0

    for s in variable:
        amounts[s.name] = down[s.name]

    return [Allocation(s.name, amounts[s.name]) for s in shares]
