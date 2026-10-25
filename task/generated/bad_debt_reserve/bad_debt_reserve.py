"""Expected credit-loss reserve for open freight receivables.

The finance team books a bad-debt reserve each close based on invoice age, customer
risk class, and expected recovery from collateral or offsets. The calculation is
performed per receivable, then rounded to cents and summed elsewhere.

Business rules:
- Negative balances are credits and reserve at zero.
- A receivable fully covered by a valid letter of credit reserves at zero.
- Aging uses whole days between invoice date and the as-of date; future-dated
  invoices are treated as current.
- Base loss rates by days past invoice date are: 0-30 0.5%, 31-60 2.0%,
  61-90 7.5%, 91-120 20.0%, over 120 45.0%.
- Risk classes adjust the base rate: low x0.7, standard x1.0, elevated x1.5,
  watchlist x2.0. The adjusted rate is capped at 95%.
- Receivables under formal dispute get a 10 percentage-point surcharge when more
  than 30 days old; the total rate remains capped at 95%.
- Small balances under $50.00 reserve at a minimum floor of $1.00 unless the
  computed reserve is zero.
- Recovery rate reduces the gross reserve after rate application. It must be from
  0 to 1 inclusive. Recovery above 80% only counts for invoices 61+ days old;
  newer invoices are limited to 80% recovery.
- Final reserve is rounded half up to the nearest cent and never exceeds the
  positive outstanding balance.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ONE = Decimal("1")
MAX_RATE = Decimal("0.95")
SMALL_BALANCE = Decimal("50.00")
MIN_SMALL_RESERVE = Decimal("1.00")

_BUCKETS = (
    (30, Decimal("0.005")),
    (60, Decimal("0.020")),
    (90, Decimal("0.075")),
    (120, Decimal("0.200")),
    (10**9, Decimal("0.450")),
)
_RISK_MULTIPLIER = {
    "low": Decimal("0.7"),
    "standard": Decimal("1.0"),
    "elevated": Decimal("1.5"),
    "watchlist": Decimal("2.0"),
}


@dataclass(frozen=True)
class Receivable:
    invoice_date: date
    as_of_date: date
    balance: Decimal
    risk_class: str = "standard"
    recovery_rate: Decimal = Decimal("0")
    in_dispute: bool = False
    secured_by_letter_of_credit: bool = False


@dataclass(frozen=True)
class ReservePolicy:
    small_balance_floor: Decimal = MIN_SMALL_RESERVE
    recovery_limit_current: Decimal = Decimal("0.80")
    dispute_surcharge: Decimal = Decimal("0.10")
    max_rate: Decimal = MAX_RATE


def _days_past_due(rec: Receivable) -> int:
    return max((rec.as_of_date - rec.invoice_date).days, 0)


def _base_rate(days: int) -> Decimal:
    for upper, rate in _BUCKETS:
        if days <= upper:
            return rate
    raise AssertionError("unreachable")


def _validated_recovery(rec: Receivable, policy: ReservePolicy, days: int) -> Decimal:
    recovery = rec.recovery_rate
    if recovery < Decimal("0") or recovery > ONE:
        raise ValueError(f"recovery_rate {recovery} must be between 0 and 1")
    if days < 61 and recovery > policy.recovery_limit_current:
        return policy.recovery_limit_current
    return recovery


def _loss_rate(rec: Receivable, policy: ReservePolicy, days: int) -> Decimal:
    try:
        multiplier = _RISK_MULTIPLIER[rec.risk_class]
    except KeyError as exc:
        raise ValueError(f"unknown risk_class {rec.risk_class!r}") from exc
    rate = _base_rate(days) * multiplier
    if rec.in_dispute and days > 30:
        rate += policy.dispute_surcharge
    return min(rate, policy.max_rate)


def calculate_bad_debt_reserve(
    receivable: Receivable, policy: ReservePolicy = ReservePolicy()
) -> Decimal:
    """Reserve for one receivable, in dollars rounded to the cent.

    >>> from datetime import date
    >>> calculate_bad_debt_reserve(Receivable(date(2026, 1, 1), date(2026, 2, 15), Decimal('1000.00')))
    Decimal('20.00')
    """
    if receivable.balance <= Decimal("0"):
        return Decimal("0.00")
    if receivable.secured_by_letter_of_credit:
        return Decimal("0.00")

    days = _days_past_due(receivable)
    rate = _loss_rate(receivable, policy, days)
    recovery = _validated_recovery(receivable, policy, days)

    gross = receivable.balance * rate
    net = gross * (ONE - recovery)
    amount = net.quantize(CENT, rounding=ROUND_HALF_UP)

    if amount > Decimal("0.00") and receivable.balance < SMALL_BALANCE and amount < policy.small_balance_floor:
        amount = policy.small_balance_floor
    if amount > receivable.balance:
        return receivable.balance.quantize(CENT, rounding=ROUND_HALF_UP)
    return amount
