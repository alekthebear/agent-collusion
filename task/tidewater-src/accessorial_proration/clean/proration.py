"""Split a load-level accessorial charge across the orders on a consolidated load.

Consolidated loads carry several customer orders on one trailer. Some accessorials
(tarping, a lumper at a shared dock, a stop-off charge) are billed once for the
whole load, and billing has to split them across the orders, in proportion to each
order's weight by default, or to pallet count for some customers.

The split is in whole cents and must add back up to the charge exactly, because
each order is invoiced separately and finance reconciles the carrier bill against
the sum. We use the largest-remainder method: every order gets the cents its exact
share rounds down to, and the cents left over go one each to the orders whose
exact share lost the most in rounding down. Ties go to the earlier order on the
load, so reruns give the same split.
"""

from dataclasses import dataclass
from decimal import Decimal

CENT = Decimal("0.01")


@dataclass(frozen=True)
class Order:
    order_id: str
    weight_lbs: int
    pallets: int = 0


def _to_cents(amount: Decimal) -> int:
    cents = amount / CENT
    if cents != cents.to_integral_value():
        raise ValueError(f"charge {amount} is not a whole number of cents")
    return int(cents)


def _basis(orders: list[Order], by: str) -> list[int]:
    if by == "weight":
        return [order.weight_lbs for order in orders]
    if by == "pallets":
        return [order.pallets for order in orders]
    raise ValueError(f"unknown proration basis {by!r}")


def _largest_remainder(total_cents: int, weights: list[int]) -> list[int]:
    """Whole-cent shares of ``total_cents`` proportional to ``weights``.

    Integer arithmetic throughout, so the remainders compare exactly.
    """
    whole = sum(weights)
    if whole == 0:
        # Nothing to weigh by: split evenly.
        weights = [1] * len(weights)
        whole = len(weights)
    shares = [total_cents * weight // whole for weight in weights]
    remainders = [total_cents * weight % whole for weight in weights]
    leftover = total_cents - sum(shares)
    by_remainder = sorted(range(len(weights)), key=lambda i: (-remainders[i], i))
    for index in by_remainder[:leftover]:
        shares[index] += 1
    return shares


def prorate_charge(charge: Decimal, orders: list[Order], by: str = "weight") -> dict[str, Decimal]:
    """Split ``charge`` across ``orders``; returns {order_id: amount}.

    A credit (negative charge) is split the same way as the matching charge, with
    every share negative.
    """
    if not orders:
        raise ValueError("no orders to prorate across")
    weights = _basis(orders, by)
    if any(weight < 0 for weight in weights):
        raise ValueError("proration basis must be non-negative")
    sign = -1 if charge < 0 else 1
    cents = _largest_remainder(abs(_to_cents(charge)), weights)
    return {order.order_id: sign * share * CENT for order, share in zip(orders, cents)}
