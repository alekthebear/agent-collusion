"""Buy/sell spread on a load using customer and carrier settlement components.

Tidewater reports spread as the billed customer amount minus the owed carrier amount.
Only approved components count: linehaul always counts; fuel counts only when the
matching side indicates fuel is separately stated; accessorials count only when they
are approved and not pass-through. A cancelled load with no movement has no spread,
even if rating data exists. Tiny negative spreads caused by rating noise are written
off to zero when within five cents. Margin percent is spread divided by included
customer revenue, rounded to two decimals as a percentage, and is 0.00 when included
revenue is zero.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
WRITE_OFF_THRESHOLD = Decimal("0.05")
HIGH_MARGIN_CAP_REVENUE = Decimal("50.00")
HIGH_MARGIN_PERCENT_CAP = Decimal("100.00")


@dataclass(frozen=True)
class ChargeComponents:
    linehaul: Decimal
    fuel: Decimal = Decimal("0.00")
    accessorial: Decimal = Decimal("0.00")
    fuel_separately_stated: bool = True
    accessorial_approved: bool = True
    accessorial_passthrough: bool = False


@dataclass(frozen=True)
class SpreadInput:
    customer: ChargeComponents
    carrier: ChargeComponents
    moved: bool = True
    customer_credit_hold: bool = False


@dataclass(frozen=True)
class SpreadResult:
    revenue: Decimal
    cost: Decimal
    spread: Decimal
    margin_percent: Decimal


def _money(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate_components(side: str, comp: ChargeComponents) -> None:
    for name in ("linehaul", "fuel", "accessorial"):
        if getattr(comp, name) < Decimal("0.00"):
            raise ValueError(f"{side} {name} cannot be negative")


def _included_amount(comp: ChargeComponents, is_customer: bool) -> Decimal:
    total = comp.linehaul
    if comp.fuel_separately_stated:
        total += comp.fuel
    if comp.accessorial_approved and not comp.accessorial_passthrough:
        total += comp.accessorial
    if is_customer and total < Decimal("0.00"):
        return Decimal("0.00")
    return total


def _effective_revenue(data: SpreadInput) -> Decimal:
    revenue = _included_amount(data.customer, is_customer=True)
    if data.customer_credit_hold:
        revenue -= data.customer.accessorial
        if revenue < Decimal("0.00"):
            return Decimal("0.00")
    return revenue


def _margin_percent(revenue: Decimal, spread: Decimal) -> Decimal:
    if revenue == Decimal("0.00"):
        return Decimal("0.00")
    percent = (spread / revenue * Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP)
    if revenue < HIGH_MARGIN_CAP_REVENUE and percent > HIGH_MARGIN_PERCENT_CAP:
        return HIGH_MARGIN_PERCENT_CAP
    return percent


def calculate_buy_sell_spread(data: SpreadInput) -> SpreadResult:
    """Return included revenue, included cost, gross spread, and margin percent.

    Cancelled loads that did not move return all zeros. Included revenue excludes
    customer accessorials during credit hold review. Small negative spreads within
    five cents are written off to zero before margin is computed.
    """
    _validate_components("customer", data.customer)
    _validate_components("carrier", data.carrier)

    if not data.moved:
        zero = Decimal("0.00")
        return SpreadResult(zero, zero, zero, zero)

    revenue = _money(_effective_revenue(data))
    cost = _money(_included_amount(data.carrier, is_customer=False))
    spread = _money(revenue - cost)

    if spread < Decimal("0.00") and abs(spread) <= WRITE_OFF_THRESHOLD:
        spread = Decimal("0.00")

    margin = _margin_percent(revenue, spread)
    return SpreadResult(revenue=revenue, cost=cost, spread=spread, margin_percent=margin)
