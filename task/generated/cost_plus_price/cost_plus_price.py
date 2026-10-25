"""Cost-plus sell pricing for brokerage quotes.

When quoting a customer, pricing starts from either the carrier's buy rate or a modeled
internal cost. The chosen base cost may include fuel and accessorial estimates depending
on the lane's pricing policy. A margin is then added using either a markup percentage on
cost or a fixed dollar adder. Markups are tiered by shipment cost because small loads
need higher percentages to cover overhead. Expedited freight carries an extra surcharge,
but a customer-specific floor margin still applies. The result is rounded to the cent and
never allowed below the included cost plus the required floor margin.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
LOW_COST_BREAK = Decimal("500.00")
MID_COST_BREAK = Decimal("1500.00")
LOW_MARKUP = Decimal("0.18")
MID_MARKUP = Decimal("0.12")
HIGH_MARKUP = Decimal("0.08")
EXPEDITE_SURCHARGE = Decimal("75.00")
MIN_SELL_PRICE = Decimal("50.00")


@dataclass(frozen=True)
class QuoteCost:
    carrier_cost: Decimal | None = None
    modeled_cost: Decimal | None = None
    fuel_surcharge: Decimal = Decimal("0.00")
    accessorials: Decimal = Decimal("0.00")
    expedited: bool = False


@dataclass(frozen=True)
class PricingPolicy:
    use_modeled_when_present: bool = False
    include_fuel: bool = True
    include_accessorials: bool = True
    fixed_margin_adder: Decimal | None = None
    minimum_margin: Decimal = Decimal("35.00")


def _validate(quote: QuoteCost, policy: PricingPolicy) -> None:
    for name, value in (
        ("carrier_cost", quote.carrier_cost),
        ("modeled_cost", quote.modeled_cost),
        ("fuel_surcharge", quote.fuel_surcharge),
        ("accessorials", quote.accessorials),
        ("minimum_margin", policy.minimum_margin),
        ("fixed_margin_adder", policy.fixed_margin_adder),
    ):
        if value is not None and value < 0:
            raise ValueError(f"{name} cannot be negative: {value}")
    if quote.carrier_cost is None and quote.modeled_cost is None:
        raise ValueError("either carrier_cost or modeled_cost is required")


def _base_linehaul_cost(quote: QuoteCost, policy: PricingPolicy) -> Decimal:
    if policy.use_modeled_when_present and quote.modeled_cost is not None:
        return quote.modeled_cost
    if quote.carrier_cost is not None:
        return quote.carrier_cost
    return quote.modeled_cost  # validated above


def _included_cost(quote: QuoteCost, policy: PricingPolicy) -> Decimal:
    cost = _base_linehaul_cost(quote, policy)
    if policy.include_fuel:
        cost += quote.fuel_surcharge
    if policy.include_accessorials:
        cost += quote.accessorials
    return cost


def _markup_rate(cost: Decimal) -> Decimal:
    if cost <= LOW_COST_BREAK:
        return LOW_MARKUP
    if cost <= MID_COST_BREAK:
        return MID_MARKUP
    return HIGH_MARKUP


def _margin_amount(cost: Decimal, quote: QuoteCost, policy: PricingPolicy) -> Decimal:
    if policy.fixed_margin_adder is not None:
        margin = policy.fixed_margin_adder
    else:
        margin = cost * _markup_rate(cost)
    if quote.expedited:
        margin += EXPEDITE_SURCHARGE
    if margin < policy.minimum_margin:
        margin = policy.minimum_margin
    return margin


def calculate_cost_plus_price(
    quote: QuoteCost, policy: PricingPolicy = PricingPolicy()
) -> Decimal:
    """Return the customer sell price in dollars, rounded half up to the cent.

    The included cost is the selected linehaul cost plus configured components. Margin
    comes from either tiered cost markup or a fixed dollar adder. Expedited loads add
    a surcharge to margin. The final sell price cannot be less than included cost plus
    the policy minimum margin, and is also subject to a small absolute sell floor.
    """
    _validate(quote, policy)
    cost = _included_cost(quote, policy)
    margin = _margin_amount(cost, quote, policy)
    sell = cost + margin
    floor_sell = cost + policy.minimum_margin
    if sell < floor_sell:
        sell = floor_sell
    if sell < MIN_SELL_PRICE:
        sell = MIN_SELL_PRICE
    return sell.quantize(CENT, rounding=ROUND_HALF_UP)
