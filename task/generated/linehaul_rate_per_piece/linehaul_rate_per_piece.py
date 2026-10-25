"""Linehaul rate per piece for LTL-style shipments.

Business rules:
- Rating starts from a tariff selected by service level. The tariff is a dollar amount
  per piece, not per hundredweight.
- Piece-count breaks reward larger shipments. Standard service uses the lower tariff
  once piece count reaches 10, 25, and 50 pieces. Expedited service has smaller
  discounts at the same breaks.
- Oversize freight is harder to handle. If the average piece weight exceeds 150 lb,
  add a 12% handling premium after tariff selection. At exactly 150 lb, no premium
  applies.
- A stop with a liftgate adds $2.25 per piece, but not above a stop-level liftgate
  cap. This charge is included before shipment minimums are checked.
- Residential delivery adds a flat $18.00 shipment surcharge.
- Every shipment must meet a shipment-level minimum charge. Standard shipments use
  a $95.00 minimum, expedited shipments use $140.00. A one-piece shipment uses a
  higher minimum because single-piece tenders are inefficient: $110.00 standard,
  $155.00 expedited.
- The returned result is the total shipment linehaul divided by pieces, rounded to
  the cent with half-up rounding.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
LIFTGATE_PER_PIECE = Decimal("2.25")
LIFTGATE_CAP = Decimal("45.00")
RESIDENTIAL_SURCHARGE = Decimal("18.00")
OVERSIZE_PREMIUM = Decimal("0.12")

STANDARD_BREAKS = ((50, Decimal("8.40")), (25, Decimal("9.10")), (10, Decimal("9.85")))
EXPEDITED_BREAKS = ((50, Decimal("11.30")), (25, Decimal("11.90")), (10, Decimal("12.45")))
STANDARD_BASE = Decimal("10.50")
EXPEDITED_BASE = Decimal("13.20")


@dataclass(frozen=True)
class ShipmentPieces:
    pieces: int
    total_weight_lb: int
    service_level: str = "standard"
    has_liftgate: bool = False
    residential_delivery: bool = False


@dataclass(frozen=True)
class LinehaulTerms:
    standard_minimum: Decimal = Decimal("95.00")
    expedited_minimum: Decimal = Decimal("140.00")
    standard_single_piece_minimum: Decimal = Decimal("110.00")
    expedited_single_piece_minimum: Decimal = Decimal("155.00")


def _validate(shipment: ShipmentPieces) -> None:
    if shipment.pieces <= 0:
        raise ValueError("pieces must be positive")
    if shipment.total_weight_lb <= 0:
        raise ValueError("total_weight_lb must be positive")
    if shipment.service_level not in {"standard", "expedited"}:
        raise ValueError(f"unsupported service_level {shipment.service_level!r}")


def _base_rate_per_piece(shipment: ShipmentPieces) -> Decimal:
    if shipment.service_level == "standard":
        base = STANDARD_BASE
        breaks = STANDARD_BREAKS
    else:
        base = EXPEDITED_BASE
        breaks = EXPEDITED_BREAKS
    for threshold, rate in breaks:
        if shipment.pieces >= threshold:
            return rate
    return base


def _minimum_charge(shipment: ShipmentPieces, terms: LinehaulTerms) -> Decimal:
    if shipment.service_level == "standard":
        return terms.standard_single_piece_minimum if shipment.pieces == 1 else terms.standard_minimum
    return terms.expedited_single_piece_minimum if shipment.pieces == 1 else terms.expedited_minimum


def _liftgate_charge(shipment: ShipmentPieces) -> Decimal:
    if not shipment.has_liftgate:
        return Decimal("0.00")
    charge = LIFTGATE_PER_PIECE * shipment.pieces
    return LIFTGATE_CAP if charge > LIFTGATE_CAP else charge


def _subtotal_before_minimum(shipment: ShipmentPieces) -> Decimal:
    rate = _base_rate_per_piece(shipment)
    linehaul = rate * shipment.pieces
    average_weight = Decimal(shipment.total_weight_lb) / Decimal(shipment.pieces)
    if average_weight > Decimal("150"):
        linehaul = linehaul * (Decimal("1.00") + OVERSIZE_PREMIUM)
    subtotal = linehaul + _liftgate_charge(shipment)
    if shipment.residential_delivery:
        subtotal += RESIDENTIAL_SURCHARGE
    return subtotal.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_linehaul_rate_per_piece(
    shipment: ShipmentPieces, terms: LinehaulTerms = LinehaulTerms()
) -> Decimal:
    """Return the billed shipment linehaul divided by piece count.

    The total shipment charge is built from the selected per-piece tariff, oversize
    premium if any, and accessorials listed in the module rules. The shipment-level
    minimum is then enforced, and the final total is divided by piece count and
    rounded half up to the cent.
    """
    _validate(shipment)
    total = _subtotal_before_minimum(shipment)
    minimum = _minimum_charge(shipment, terms)
    if total < minimum:
        total = minimum
    return (total / Decimal(shipment.pieces)).quantize(CENT, rounding=ROUND_HALF_UP)
