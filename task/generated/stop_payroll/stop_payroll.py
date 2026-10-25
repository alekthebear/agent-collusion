"""Driver stop payroll for compensated pickup and delivery activity.

Tidewater pays stop money on loads with many customer-facing stops, but not every stop on
a route counts. Fuel, scale, yard, washout, and relay stops are excluded. The first two
compensated stops on a load are considered covered by mileage and do not earn stop pay.
Each additional compensated stop pays a flat rate. Team trucks split stop pay evenly across
qualifying paid stops. Trainer trucks do not split; the trainer receives full stop pay and the
trainee receives none. Customer-requested redelivery counts as two compensated stops because
it requires a second attempt. Amounts are rounded to cents, and negative rates or impossible
configurations are rejected.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
DEFAULT_RATE = Decimal("25.00")
EXCLUDED_TYPES = frozenset({"fuel", "scale", "yard", "washout", "relay"})
REDLIVERY_BONUS_COUNT = 2
FREE_COMPENSATED_STOPS = 2


@dataclass(frozen=True)
class StopRecord:
    """One stop on the load.

    ``stop_type`` is compared case-insensitively after trimming spaces.
    ``customer_requested_redelivery`` counts this stop as two compensated stops when the
    stop is otherwise eligible.
    """

    stop_type: str
    customer_requested_redelivery: bool = False


@dataclass(frozen=True)
class PayrollTerms:
    stop_rate: Decimal = DEFAULT_RATE
    free_compensated_stops: int = FREE_COMPENSATED_STOPS
    team_split: bool = False
    trainer_truck: bool = False


def _normalize_stop_type(stop_type: str) -> str:
    normalized = stop_type.strip().lower()
    if not normalized:
        raise ValueError("stop_type must not be blank")
    return normalized


def _validate_terms(terms: PayrollTerms) -> None:
    if terms.stop_rate < 0:
        raise ValueError("stop_rate must be non-negative")
    if terms.free_compensated_stops < 0:
        raise ValueError("free_compensated_stops must be non-negative")
    if terms.team_split and terms.trainer_truck:
        raise ValueError("team_split and trainer_truck cannot both be enabled")


def _compensated_count(stops: list[StopRecord]) -> int:
    count = 0
    for stop in stops:
        stop_type = _normalize_stop_type(stop.stop_type)
        if stop_type in EXCLUDED_TYPES:
            continue
        if stop.customer_requested_redelivery:
            count += REDLIVERY_BONUS_COUNT
        else:
            count += 1
    return count


def _paid_stop_count(compensated_count: int, free_compensated_stops: int) -> int:
    if compensated_count <= free_compensated_stops:
        return 0
    return compensated_count - free_compensated_stops


def _split_amount(amount: Decimal, team_split: bool) -> Decimal:
    if not team_split:
        return amount
    return (amount / 2).quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_stop_payroll(
    stops: list[StopRecord], terms: PayrollTerms = PayrollTerms()
) -> Decimal:
    """Return stop pay owed to one driver for the load.

    Only compensated pickup and delivery activity counts. Excluded stop types earn no stop
    pay and do not consume the free-stop allowance. The first ``terms.free_compensated_stops``
    compensated stops are unpaid; each additional compensated stop pays ``terms.stop_rate``.
    Team trucks split the resulting amount evenly. Trainer trucks pay the trainer the full
    amount with no split.
    """
    _validate_terms(terms)
    compensated = _compensated_count(stops)
    paid_stops = _paid_stop_count(compensated, terms.free_compensated_stops)
    if paid_stops == 0 or terms.stop_rate == 0:
        return Decimal("0.00")
    amount = (terms.stop_rate * paid_stops).quantize(CENT, rounding=ROUND_HALF_UP)
    return _split_amount(amount, terms.team_split)
