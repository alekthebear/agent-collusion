"""Owner-operator share of billed fuel surcharge on a settled load.

Tidewater pays owner-operators a contractual share of the customer fuel surcharge
(FSC), but not every billed FSC dollar is always shareable. Contracts may exclude
empty-mile FSC from the contractor payout, and short or local moves can have a
minimum retained by the carrier so tiny FSC amounts do not create penny noise on
settlement.

Business rules implemented here:
- ``billed_fsc`` is the total fuel surcharge billed on the load and must be >= 0.
- ``loaded_miles`` must be >= 0. ``empty_miles`` must be >= 0.
- ``share_percent`` is the contractor split as a percent from 0 through 100.
- If the contract excludes empty miles, only the loaded-mile portion of billed FSC
  is shareable. The split uses loaded miles divided by total dispatched miles.
- If total miles are zero, no FSC is shareable regardless of the billed amount.
- If loaded miles are zero, no FSC is shareable when empty miles are excluded.
- Loads with loaded miles under 50 are treated as local and the carrier retains the
  first $5.00 of otherwise shareable FSC before applying the split.
- Loads with loaded miles from 50 through 149 retain the first $2.50.
- No retention applies at 150 loaded miles and above.
- After the split, payouts under $1.00 are rounded down to $0.00 as de minimis.
- Final amounts are rounded to the nearest cent using half-up rounding.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
LOCAL_RETAIN = Decimal("5.00")
SHORT_RETAIN = Decimal("2.50")
DE_MINIMIS = Decimal("1.00")


@dataclass(frozen=True)
class FuelShareInputs:
    billed_fsc: Decimal
    loaded_miles: int
    empty_miles: int = 0
    include_empty_miles: bool = True


@dataclass(frozen=True)
class FuelShareTerms:
    share_percent: Decimal = Decimal("65.0")


def _validate(inputs: FuelShareInputs, terms: FuelShareTerms) -> None:
    if inputs.billed_fsc < 0:
        raise ValueError("billed_fsc must be non-negative")
    if inputs.loaded_miles < 0:
        raise ValueError("loaded_miles must be non-negative")
    if inputs.empty_miles < 0:
        raise ValueError("empty_miles must be non-negative")
    if terms.share_percent < 0 or terms.share_percent > 100:
        raise ValueError("share_percent must be between 0 and 100")


def _retained_amount(loaded_miles: int) -> Decimal:
    if loaded_miles < 50:
        return LOCAL_RETAIN
    if loaded_miles < 150:
        return SHORT_RETAIN
    return Decimal("0.00")


def _shareable_fsc(inputs: FuelShareInputs) -> Decimal:
    total_miles = inputs.loaded_miles + inputs.empty_miles
    if total_miles == 0:
        return Decimal("0.00")
    if inputs.include_empty_miles:
        base = inputs.billed_fsc
    else:
        if inputs.loaded_miles == 0:
            return Decimal("0.00")
        ratio = Decimal(inputs.loaded_miles) / Decimal(total_miles)
        base = inputs.billed_fsc * ratio
    retained = _retained_amount(inputs.loaded_miles)
    if base <= retained:
        return Decimal("0.00")
    return base - retained


def _round_money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_owner_operator_fuel_share(
    inputs: FuelShareInputs, terms: FuelShareTerms = FuelShareTerms()
) -> Decimal:
    """Owner-operator fuel surcharge share for one settled load.

    The function first determines the shareable portion of billed FSC based on
    whether empty-mile FSC is included, subtracts any carrier retention for local
    or short loaded moves, applies the contractual split percentage, then rounds to
    cents. Results below $1.00 after the split are paid as $0.00.
    """
    _validate(inputs, terms)
    shareable = _shareable_fsc(inputs)
    if shareable == 0:
        return Decimal("0.00")
    payout = shareable * terms.share_percent / Decimal("100")
    payout = _round_money(payout)
    if payout < DE_MINIMIS:
        return Decimal("0.00")
    return payout
