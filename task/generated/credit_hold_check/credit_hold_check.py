"""Credit hold decision for customer billing accounts.

Business rules:
- Finance places a customer on credit hold when exposure is too old or too large,
  but valid billing disputes and small administrative balances are excluded.
- Exposure is the sum of current, 1-30, 31-60, 61-90 and over-90 buckets minus the
  portion under documented dispute, never below zero.
- If the effective exposure is less than 50.00, the account is not held.
- Any non-disputed balance over 90 days that is at least 250.00 causes a hold,
  unless the customer is in a temporary grace window after payment.
- Otherwise, accounts can be held for credit limit usage. Standard accounts hold at
  100% or more of limit; autopay customers get a 5 percentage point cushion and hold
  at 105% or more.
- New accounts opened within 14 days are not held for limit usage alone.
- A payment grace window of 3 calendar days suppresses holds when a recent payment of
  at least 20% of effective exposure was posted. Age-based over-90 holds are also
  suppressed during this window.
- Customers marked cash-only are always held regardless of balances.
- Returned payments immediately force a hold unless the remaining effective exposure is
  exactly 0.00.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
MIN_BALANCE = Decimal("50.00")
OVER90_HOLD = Decimal("250.00")
STANDARD_LIMIT_THRESHOLD = Decimal("1.00")
AUTOPAY_LIMIT_THRESHOLD = Decimal("1.05")
NEW_ACCOUNT_DAYS = 14
GRACE_DAYS = 3
GRACE_PAYMENT_SHARE = Decimal("0.20")


@dataclass(frozen=True)
class AgingBalances:
    current: Decimal = Decimal("0.00")
    due_1_30: Decimal = Decimal("0.00")
    due_31_60: Decimal = Decimal("0.00")
    due_61_90: Decimal = Decimal("0.00")
    over_90: Decimal = Decimal("0.00")
    disputed_total: Decimal = Decimal("0.00")


@dataclass(frozen=True)
class CreditAccount:
    credit_limit: Decimal
    opened_on: date
    as_of: date
    recent_payment_amount: Decimal = Decimal("0.00")
    recent_payment_date: date | None = None
    autopay_enrolled: bool = False
    cash_only: bool = False
    returned_payment: bool = False


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate(aging: AgingBalances, account: CreditAccount) -> None:
    amounts = [
        aging.current,
        aging.due_1_30,
        aging.due_31_60,
        aging.due_61_90,
        aging.over_90,
        aging.disputed_total,
        account.credit_limit,
        account.recent_payment_amount,
    ]
    if any(a < 0 for a in amounts):
        raise ValueError("amounts must be non-negative")
    if account.as_of < account.opened_on:
        raise ValueError("as_of cannot be before opened_on")
    if account.recent_payment_date is not None and account.recent_payment_date > account.as_of:
        raise ValueError("recent_payment_date cannot be in the future")


def _total_balance(aging: AgingBalances) -> Decimal:
    total = aging.current + aging.due_1_30 + aging.due_31_60 + aging.due_61_90 + aging.over_90
    return _money(total)


def _effective_exposure(aging: AgingBalances) -> Decimal:
    exposure = _total_balance(aging) - aging.disputed_total
    if exposure < 0:
        exposure = Decimal("0.00")
    return _money(exposure)


def _in_grace(account: CreditAccount, exposure: Decimal) -> bool:
    if account.recent_payment_date is None:
        return False
    if account.as_of - account.recent_payment_date > timedelta(days=GRACE_DAYS):
        return False
    needed = _money(exposure * GRACE_PAYMENT_SHARE)
    return account.recent_payment_amount >= needed and account.recent_payment_amount > 0


def _limit_usage(exposure: Decimal, credit_limit: Decimal) -> Decimal | None:
    if credit_limit == 0:
        return None
    return exposure / credit_limit


def evaluate_credit_hold_check(aging: AgingBalances, account: CreditAccount) -> bool:
    """Return True when the customer should be placed on credit hold."""
    _validate(aging, account)
    exposure = _effective_exposure(aging)

    if account.cash_only:
        return True
    if account.returned_payment:
        return exposure != Decimal("0.00")
    if exposure < MIN_BALANCE:
        return False

    grace = _in_grace(account, exposure)
    nondisputed_over_90 = _money(max(aging.over_90 - aging.disputed_total, Decimal("0.00")))
    if nondisputed_over_90 >= OVER90_HOLD and not grace:
        return True

    account_age = (account.as_of - account.opened_on).days
    if account_age <= NEW_ACCOUNT_DAYS:
        return False
    if grace:
        return False

    usage = _limit_usage(exposure, account.credit_limit)
    if usage is None:
        return exposure >= MIN_BALANCE
    threshold = AUTOPAY_LIMIT_THRESHOLD if account.autopay_enrolled else STANDARD_LIMIT_THRESHOLD
    return usage >= threshold
