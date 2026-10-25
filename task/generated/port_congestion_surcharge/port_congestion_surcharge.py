"""Port congestion surcharges for dray moves at marine terminals.

Tidewater bills a congestion surcharge when a move touches a terminal operating under
an elevated congestion tier. The amount depends on the transaction type, the terminal's
published tier on the service date, and whether the carrier absorbed avoidable delay.

Business rules used by billing:
- No surcharge applies before the terminal program effective date.
- Transaction base charges by tier are: import/export tier 1 = $35, tier 2 = $60,
  tier 3 = $95; empty returns/pickups use 50% of the import/export base.
- Street turns do not incur the surcharge.
- Weekend gates add $20 at tier 2 or 3, but not at tier 1.
- If the driver had an appointment and arrived more than 30 minutes late, reduce the
  surcharge by 50% because the missed window is treated as carrier-caused delay.
- If the terminal delay after the appointment exceeds 3 hours, add a severe congestion
  premium of $25, but only on or after 2026-07-01.
- Hazardous moves add $15, except empty transactions never get the hazmat add-on.
- Partner terminals may cap the total surcharge at a per-move maximum.
- Final billed amount is rounded to the nearest cent using half-up rounding.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

PROGRAM_EFFECTIVE_DATE = date(2026, 4, 1)
SEVERE_DELAY_EFFECTIVE_DATE = date(2026, 7, 1)
CENT = Decimal("0.01")

_BASE_BY_TIER = {
    1: Decimal("35.00"),
    2: Decimal("60.00"),
    3: Decimal("95.00"),
}
_EMPTY_FACTOR = Decimal("0.50")
_WEEKEND_PREMIUM = Decimal("20.00")
_HAZMAT_PREMIUM = Decimal("15.00")
_SEVERE_DELAY_PREMIUM = Decimal("25.00")
_LATE_REDUCTION_FACTOR = Decimal("0.50")


@dataclass(frozen=True)
class CongestionMove:
    service_date: date
    transaction_type: str
    congestion_tier: int
    gate_time: datetime
    appointment_time: datetime | None = None
    arrival_time: datetime | None = None
    hazardous: bool = False
    terminal_cap: Decimal | None = None


@dataclass(frozen=True)
class CongestionTerms:
    program_effective_date: date = PROGRAM_EFFECTIVE_DATE
    severe_delay_effective_date: date = SEVERE_DELAY_EFFECTIVE_DATE


def _validate(move: CongestionMove) -> None:
    if move.congestion_tier not in _BASE_BY_TIER:
        raise ValueError(f"unsupported congestion tier {move.congestion_tier}")
    if move.transaction_type not in {"import", "export", "empty", "street_turn"}:
        raise ValueError(f"unsupported transaction type {move.transaction_type!r}")
    if move.appointment_time is None and move.arrival_time is not None:
        raise ValueError("arrival_time requires appointment_time")
    if move.appointment_time is not None and move.arrival_time is None:
        raise ValueError("appointment_time requires arrival_time")
    if (
        move.appointment_time is not None
        and move.arrival_time is not None
        and move.gate_time < move.arrival_time
    ):
        raise ValueError("gate_time is before arrival_time")
    if move.terminal_cap is not None and move.terminal_cap < Decimal("0.00"):
        raise ValueError("terminal_cap cannot be negative")


def _base_amount(move: CongestionMove) -> Decimal:
    if move.transaction_type == "street_turn":
        return Decimal("0.00")
    base = _BASE_BY_TIER[move.congestion_tier]
    if move.transaction_type == "empty":
        return base * _EMPTY_FACTOR
    return base


def _is_weekend(gate_time: datetime) -> bool:
    return gate_time.weekday() >= 5


def _late_arrival_reduction_applies(move: CongestionMove) -> bool:
    if move.appointment_time is None or move.arrival_time is None:
        return False
    delay_minutes = (move.arrival_time - move.appointment_time).total_seconds() / 60
    return delay_minutes > 30


def _severe_delay_premium_applies(move: CongestionMove, terms: CongestionTerms) -> bool:
    if move.service_date < terms.severe_delay_effective_date:
        return False
    if move.appointment_time is None:
        return False
    delay_hours = (move.gate_time - move.appointment_time).total_seconds() / 3600
    return delay_hours > 3


def _apply_cap(amount: Decimal, cap: Decimal | None) -> Decimal:
    if cap is not None and amount > cap:
        return cap
    return amount


def calculate_port_congestion_surcharge(
    move: CongestionMove, terms: CongestionTerms = CongestionTerms()
) -> Decimal:
    """Return the billed port congestion surcharge for one move."""
    _validate(move)
    if move.service_date < terms.program_effective_date:
        return Decimal("0.00")

    amount = _base_amount(move)
    if amount == Decimal("0.00"):
        return amount

    if _is_weekend(move.gate_time) and move.congestion_tier >= 2:
        amount += _WEEKEND_PREMIUM
    if move.hazardous and move.transaction_type != "empty":
        amount += _HAZMAT_PREMIUM
    if _severe_delay_premium_applies(move, terms):
        amount += _SEVERE_DELAY_PREMIUM
    if _late_arrival_reduction_applies(move):
        amount *= _LATE_REDUCTION_FACTOR

    amount = amount.quantize(CENT, rounding=ROUND_HALF_UP)
    return _apply_cap(amount, move.terminal_cap)
