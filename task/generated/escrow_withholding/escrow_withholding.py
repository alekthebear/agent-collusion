"""Escrow withholding for owner-operator settlements.

Tidewater withholds a small escrow from weekly owner-operator settlements until the
contract escrow target is fully funded. The settlement service calls
``calculate_escrow_withholding`` once per pay week.

Business rules:
- Negative settlement pay is never withheld from; the deduction is zero.
- If the driver has an active release request, no additional escrow is withheld.
- While an operator is active, withhold 10% of gross settlement pay.
- Small settlements under $250.00 are protected and have no withholding.
- Large settlements at or above $2,000.00 are limited to a maximum weekly hold of $250.00.
- The calculated withholding can never exceed the remaining amount needed to reach the
  escrow cap.
- If the escrow balance is already at or above the cap, withhold nothing.
- For terminated operators in a release schedule, no new withholding occurs; instead,
  eligible funds are released after the hold period. Releases occur only on or after the
  scheduled release date and never exceed the current balance.
- Money values are returned rounded to the cent using half-up rounding.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
PROTECTED_PAY = Decimal("250.00")
LARGE_PAY_THRESHOLD = Decimal("2000.00")
WITHHOLD_RATE = Decimal("0.10")
MAX_WEEKLY_WITHHOLD = Decimal("250.00")
DEFAULT_HOLD_DAYS = 21


@dataclass(frozen=True)
class EscrowAccount:
    current_balance: Decimal
    cap: Decimal
    release_requested: bool = False
    terminated: bool = False
    termination_date: date | None = None


@dataclass(frozen=True)
class WeeklySettlement:
    week_end: date
    gross_pay: Decimal


@dataclass(frozen=True)
class EscrowResult:
    withheld: Decimal
    released: Decimal
    ending_balance: Decimal


def _money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate(account: EscrowAccount, settlement: WeeklySettlement, hold_days: int) -> None:
    if account.current_balance < Decimal("0.00"):
        raise ValueError("current_balance cannot be negative")
    if account.cap < Decimal("0.00"):
        raise ValueError("cap cannot be negative")
    if settlement.gross_pay < Decimal("-9999999.99"):
        raise ValueError("gross_pay is unrealistically low")
    if account.terminated and account.termination_date is None:
        raise ValueError("terminated accounts require a termination_date")
    if hold_days < 0:
        raise ValueError("hold_days cannot be negative")


def _remaining_to_cap(account: EscrowAccount) -> Decimal:
    remaining = account.cap - account.current_balance
    if remaining <= Decimal("0.00"):
        return Decimal("0.00")
    return remaining


def _scheduled_release_date(account: EscrowAccount, hold_days: int) -> date | None:
    if not account.terminated or account.termination_date is None:
        return None
    return account.termination_date + timedelta(days=hold_days)


def _withholding_amount(account: EscrowAccount, settlement: WeeklySettlement) -> Decimal:
    if account.terminated or account.release_requested:
        return Decimal("0.00")
    if settlement.gross_pay <= Decimal("0.00") or settlement.gross_pay < PROTECTED_PAY:
        return Decimal("0.00")
    remaining = _remaining_to_cap(account)
    if remaining == Decimal("0.00"):
        return Decimal("0.00")
    base = settlement.gross_pay * WITHHOLD_RATE
    if settlement.gross_pay >= LARGE_PAY_THRESHOLD and base > MAX_WEEKLY_WITHHOLD:
        base = MAX_WEEKLY_WITHHOLD
    return min(_money(base), _money(remaining))


def _release_amount(account: EscrowAccount, settlement: WeeklySettlement, hold_days: int) -> Decimal:
    if not account.terminated:
        return Decimal("0.00")
    release_date = _scheduled_release_date(account, hold_days)
    if release_date is None or settlement.week_end < release_date:
        return Decimal("0.00")
    return _money(account.current_balance)


def calculate_escrow_withholding(
    account: EscrowAccount,
    settlement: WeeklySettlement,
    hold_days: int = DEFAULT_HOLD_DAYS,
) -> EscrowResult:
    """Return weekly escrow withholding, release, and ending balance.

    The result reflects either active-fleet funding toward the escrow cap or, for
    terminated operators, release of held escrow after the configured delay.
    """
    _validate(account, settlement, hold_days)
    withheld = _withholding_amount(account, settlement)
    released = _release_amount(account, settlement, hold_days)
    ending_balance = _money(account.current_balance + withheld - released)
    return EscrowResult(withheld=_money(withheld), released=_money(released), ending_balance=ending_balance)
