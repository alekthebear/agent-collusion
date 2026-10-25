"""Payroll allocation between trainer and trainee for over-the-road training loads.

Tidewater pays one linehaul amount for a training trip, then allocates that pay between
trainer and trainee based on program phase and miles driven. Business rules:

* Empty or nonpositive-pay trips allocate nothing to either party.
* Orientation phase pays 100% to the trainer regardless of miles.
* For active driving phases, only loaded and authorized empty miles are eligible.
  Unauthorized empty miles are excluded from both the split denominator and any minimum
  participation test.
* The trainee's share is based on the program phase percentage, but only if the trainee
  drove at least a minimum share of eligible miles in that phase.
* If the trainee misses the minimum by less than 5 percentage points, the trainee keeps
  half of the normal phase percentage as a soft landing; otherwise the trainer receives
  the full amount.
* Team-drive phase with fewer than 50 eligible miles is treated as a trainer-only trip.
* Amounts are rounded to the cent with half-up rounding, and the two amounts always sum
  to the rounded trip pay.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")

_PHASE_TRAINEE_PERCENT = {
    "orientation": Decimal("0.00"),
    "seat1": Decimal("0.25"),
    "seat2": Decimal("0.40"),
    "team": Decimal("0.50"),
}

_PHASE_MIN_SHARE = {
    "orientation": Decimal("0.00"),
    "seat1": Decimal("0.20"),
    "seat2": Decimal("0.30"),
    "team": Decimal("0.45"),
}


@dataclass(frozen=True)
class TripMiles:
    loaded_miles: int
    authorized_empty_miles: int = 0
    unauthorized_empty_miles: int = 0
    trainee_miles: int = 0


@dataclass(frozen=True)
class TrainingProgram:
    phase: str


@dataclass(frozen=True)
class PaySplit:
    trainer_pay: Decimal
    trainee_pay: Decimal


def _round_money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate(miles: TripMiles, program: TrainingProgram, trip_pay: Decimal) -> None:
    if program.phase not in _PHASE_TRAINEE_PERCENT:
        raise ValueError(f"unknown training phase: {program.phase}")
    for name, value in (
        ("loaded_miles", miles.loaded_miles),
        ("authorized_empty_miles", miles.authorized_empty_miles),
        ("unauthorized_empty_miles", miles.unauthorized_empty_miles),
        ("trainee_miles", miles.trainee_miles),
    ):
        if value < 0:
            raise ValueError(f"{name} must be nonnegative")
    if trip_pay < Decimal("0"):
        raise ValueError("trip_pay must be nonnegative")


def _eligible_miles(miles: TripMiles) -> int:
    return miles.loaded_miles + miles.authorized_empty_miles


def _trainee_share_ratio(miles: TripMiles) -> Decimal:
    eligible = _eligible_miles(miles)
    if eligible <= 0:
        return Decimal("0")
    driven = min(miles.trainee_miles, eligible)
    return Decimal(driven) / Decimal(eligible)


def _effective_trainee_percent(miles: TripMiles, program: TrainingProgram) -> Decimal:
    phase = program.phase
    base_percent = _PHASE_TRAINEE_PERCENT[phase]
    if base_percent == Decimal("0.00"):
        return Decimal("0.00")

    eligible = _eligible_miles(miles)
    if phase == "team" and eligible < 50:
        return Decimal("0.00")

    share = _trainee_share_ratio(miles)
    minimum = _PHASE_MIN_SHARE[phase]
    if share >= minimum:
        return base_percent

    shortfall = minimum - share
    if shortfall < Decimal("0.05"):
        return base_percent / 2
    return Decimal("0.00")


def calculate_trainer_pay_split(
    trip_pay: Decimal,
    miles: TripMiles,
    program: TrainingProgram,
) -> PaySplit:
    """Allocate one trip's pay between trainer and trainee.

    The trainee percentage depends on the training phase and whether the trainee drove
    enough of the eligible miles for that phase. Unauthorized empty miles do not count
    toward eligible miles. Returned amounts are rounded to cents and sum to the rounded
    trip pay.
    """
    _validate(miles, program, trip_pay)
    total_pay = _round_money(trip_pay)
    if total_pay == Decimal("0.00") or _eligible_miles(miles) == 0:
        return PaySplit(trainer_pay=Decimal("0.00"), trainee_pay=Decimal("0.00"))

    trainee_percent = _effective_trainee_percent(miles, program)
    trainee_pay = _round_money(total_pay * trainee_percent)
    trainer_pay = total_pay - trainee_pay
    return PaySplit(trainer_pay=trainer_pay, trainee_pay=trainee_pay)
