"""Driver-assist charges for loads that require the driver to help handle freight.

Tidewater bills driver assist when a stop requires unusual unloading help beyond a
normal dock delivery. Customers may rate assist in different ways: by pieces,
by weight, by time on site, or as a flat fee. The billing service calls
``calculate_driver_assist_fee`` once per stop.

Business rules:
- A stop is not billable unless ``assist_required`` is true.
- Flat-fee customers are billed their flat fee whenever assist is required.
- Piece-based billing charges only for pieces above the included threshold.
- Weight-based billing charges only for pounds above the included threshold, in
  started 500 lb increments.
- Time-based billing charges only for minutes above the included threshold, in
  started 15 minute increments.
- Residential stops add a surcharge when the computed fee is positive.
- Reefer unloads below 2,000 lb are waived because they are treated as ordinary
  handoff work.
- The computed amount is then raised to the contract minimum when positive and
  reduced to the contract maximum when present.
- Final amounts are rounded half up to the nearest cent.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
WEIGHT_INCREMENT = 500
TIME_INCREMENT_MINUTES = 15


@dataclass(frozen=True)
class AssistStop:
    pieces: int = 0
    weight_lb: int = 0
    assist_minutes: int = 0
    assist_required: bool = False
    residential: bool = False
    reefer: bool = False


@dataclass(frozen=True)
class DriverAssistTerms:
    billing_basis: str = "pieces"
    piece_rate: Decimal = Decimal("2.50")
    included_pieces: int = 24
    weight_rate_per_500lb: Decimal = Decimal("8.00")
    included_weight_lb: int = 1000
    time_rate_per_15min: Decimal = Decimal("12.50")
    included_minutes: int = 30
    flat_fee: Decimal = Decimal("65.00")
    minimum_charge: Decimal = Decimal("35.00")
    maximum_charge: Decimal | None = Decimal("250.00")
    residential_surcharge: Decimal = Decimal("18.50")


def _validate(stop: AssistStop, terms: DriverAssistTerms) -> None:
    if stop.pieces < 0 or stop.weight_lb < 0 or stop.assist_minutes < 0:
        raise ValueError("pieces, weight_lb, and assist_minutes must be non-negative")
    if terms.billing_basis not in {"pieces", "weight", "time", "flat"}:
        raise ValueError(f"unsupported billing_basis {terms.billing_basis!r}")


def _started_units(overage: int, size: int) -> int:
    if overage <= 0:
        return 0
    whole, partial = divmod(overage, size)
    return whole + (1 if partial else 0)


def _base_amount(stop: AssistStop, terms: DriverAssistTerms) -> Decimal:
    if terms.billing_basis == "flat":
        return terms.flat_fee
    if terms.billing_basis == "pieces":
        billable_pieces = max(0, stop.pieces - terms.included_pieces)
        return terms.piece_rate * billable_pieces
    if terms.billing_basis == "weight":
        overage = stop.weight_lb - terms.included_weight_lb
        units = _started_units(overage, WEIGHT_INCREMENT)
        return terms.weight_rate_per_500lb * units
    overage = stop.assist_minutes - terms.included_minutes
    units = _started_units(overage, TIME_INCREMENT_MINUTES)
    return terms.time_rate_per_15min * units


def _apply_bounds(amount: Decimal, terms: DriverAssistTerms) -> Decimal:
    if amount > Decimal("0.00") and amount < terms.minimum_charge:
        amount = terms.minimum_charge
    if terms.maximum_charge is not None and amount > terms.maximum_charge:
        amount = terms.maximum_charge
    return amount


def calculate_driver_assist_fee(
    stop: AssistStop, terms: DriverAssistTerms = DriverAssistTerms()
) -> Decimal:
    """Return the driver-assist fee for one stop in dollars.

    The amount is calculated from the contract billing basis, then adjusted for
    stop-specific waivers, surcharges, minimums, and maximums.
    """
    _validate(stop, terms)
    if not stop.assist_required:
        return Decimal("0.00")
    if stop.reefer and stop.weight_lb < 2000:
        return Decimal("0.00")

    amount = _base_amount(stop, terms)
    if amount > Decimal("0.00") and stop.residential:
        amount += terms.residential_surcharge
    amount = _apply_bounds(amount, terms)
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)
