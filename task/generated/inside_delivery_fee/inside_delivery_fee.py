"""Inside-delivery accessorials for shipments moved beyond the receiver's dock.

Inside delivery is billed when the consignee asks the driver to place freight inside a
building rather than leaving it at the dock or curb. Tidewater's standard rules are:

- Base fee depends on service level: threshold, room-of-choice, and white glove.
- Service includes one floor at no extra charge.
- Additional floors are billed per floor, but elevator stops reduce the per-floor charge.
- No floor surcharge applies when the destination floor is 1 or lower.
- Piece-heavy deliveries add a handling surcharge above a service-specific included count.
- White glove includes more pieces before the surcharge begins.
- Threshold deliveries with 25 or more pieces add a flat heavy-handling bump.
- The final fee is the greater of the computed amount and the contract minimum charge.
- All money is rounded half up to the nearest cent after surcharges are added.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")

BASE_BY_SERVICE = {
    "threshold": Decimal("45.00"),
    "room_of_choice": Decimal("85.00"),
    "white_glove": Decimal("140.00"),
}

EXTRA_FLOOR_RATE = {
    "threshold": Decimal("18.00"),
    "room_of_choice": Decimal("25.00"),
    "white_glove": Decimal("35.00"),
}

ELEVATOR_EXTRA_FLOOR_RATE = {
    "threshold": Decimal("10.00"),
    "room_of_choice": Decimal("14.00"),
    "white_glove": Decimal("20.00"),
}

INCLUDED_PIECES = {
    "threshold": 5,
    "room_of_choice": 10,
    "white_glove": 15,
}

PER_PIECE_SURCHARGE = Decimal("3.50")
THRESHOLD_HEAVY_HANDLING_BUMP = Decimal("10.50")
DEFAULT_MINIMUM_CHARGE = Decimal("55.00")


@dataclass(frozen=True)
class InsideDeliveryRequest:
    service_level: str
    floor_count: int
    has_elevator: bool
    piece_count: int


@dataclass(frozen=True)
class InsideDeliveryTerms:
    minimum_charge: Decimal = DEFAULT_MINIMUM_CHARGE


def _validate(request: InsideDeliveryRequest, terms: InsideDeliveryTerms) -> None:
    if request.service_level not in BASE_BY_SERVICE:
        raise ValueError(f"unknown service level: {request.service_level}")
    if request.floor_count < 0:
        raise ValueError(f"floor_count must be >= 0, got {request.floor_count}")
    if request.piece_count < 0:
        raise ValueError(f"piece_count must be >= 0, got {request.piece_count}")
    if terms.minimum_charge < Decimal("0.00"):
        raise ValueError(f"minimum_charge must be >= 0.00, got {terms.minimum_charge}")


def _extra_floors(floor_count: int) -> int:
    return max(0, floor_count - 1)


def _floor_surcharge(request: InsideDeliveryRequest) -> Decimal:
    floors = _extra_floors(request.floor_count)
    if floors == 0:
        return Decimal("0.00")
    rates = ELEVATOR_EXTRA_FLOOR_RATE if request.has_elevator else EXTRA_FLOOR_RATE
    return rates[request.service_level] * floors


def _piece_surcharge(request: InsideDeliveryRequest) -> Decimal:
    included = INCLUDED_PIECES[request.service_level]
    extra_pieces = max(0, request.piece_count - included)
    if extra_pieces == 0:
        return Decimal("0.00")
    surcharge = PER_PIECE_SURCHARGE * extra_pieces
    if request.service_level == "threshold" and request.piece_count >= 25:
        surcharge += THRESHOLD_HEAVY_HANDLING_BUMP
    return surcharge


def _rounded(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_inside_delivery_fee(
    request: InsideDeliveryRequest,
    terms: InsideDeliveryTerms = InsideDeliveryTerms(),
) -> Decimal:
    """Inside-delivery fee for one stop, in dollars.

    The fee is base service price plus floor and piece surcharges. One floor is included.
    Elevator buildings use a lower extra-floor rate. The final amount is rounded to cents,
    then raised to ``terms.minimum_charge`` if needed.
    """
    _validate(request, terms)
    amount = BASE_BY_SERVICE[request.service_level]
    amount += _floor_surcharge(request)
    amount += _piece_surcharge(request)
    amount = _rounded(amount)
    if amount < terms.minimum_charge:
        return _rounded(terms.minimum_charge)
    return amount
