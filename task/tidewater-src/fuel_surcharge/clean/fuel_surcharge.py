"""Per-mile fuel surcharge (FSC) from the weekly DOE diesel average.

The DOE publishes the national on-highway diesel average every Monday, or on
Tuesday when Monday is a federal holiday. A published price applies to every
shipment picked up from its publication date until the next publication, so a
shipment uses the most recent price published on or before its pickup date.

Most contracts, Hartline's included, use the standard table: no surcharge at or
below a $1.20 peg, then one cent per mile for every full six cents above the peg.
Billing calls ``fuel_surcharge_for_shipment``; the price history comes from the
nightly DOE import as a {publication date: price} mapping.
"""

from bisect import bisect_right
from datetime import date
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

PEG = Decimal("1.20")
STEP = Decimal("0.06")
CENTS_PER_STEP = Decimal("0.01")
CENT = Decimal("0.01")


def _as_decimal(value: Decimal | float | str) -> Decimal:
    # str() first, so a float price like 3.85 doesn't become 3.8499999...
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _publication_for(pickup: date, prices: dict[date, Decimal]) -> date:
    """The DOE publication in effect on ``pickup``: the latest one on or before it."""
    if not prices:
        raise ValueError("no DOE prices loaded")
    published = sorted(prices)
    index = bisect_right(published, pickup) - 1
    if index < 0:
        raise ValueError(f"no DOE price published on or before {pickup}")
    return published[index]


def _price_for(pickup: date, prices: dict[date, Decimal]) -> Decimal:
    return _as_decimal(prices[_publication_for(pickup, prices)])


def surcharge_per_mile(diesel_price: Decimal | float | str) -> Decimal:
    """Cents per mile from the standard table, as dollars (0.44 = 44 cents)."""
    price = _as_decimal(diesel_price)
    if price <= PEG:
        return Decimal("0.00")
    steps = ((price - PEG) / STEP).to_integral_value(rounding=ROUND_FLOOR)
    return steps * CENTS_PER_STEP


def fuel_surcharge_for_shipment(
    pickup: date, miles: Decimal | float | str, prices: dict[date, Decimal]
) -> Decimal:
    """The fuel surcharge for one shipment, in dollars rounded to the cent."""
    loaded_miles = _as_decimal(miles)
    if loaded_miles < 0:
        raise ValueError("miles must be non-negative")
    per_mile = surcharge_per_mile(_price_for(pickup, prices))
    return (per_mile * loaded_miles).quantize(CENT, rounding=ROUND_HALF_UP)


def describe_surcharge(pickup: date, prices: dict[date, Decimal]) -> str:
    """The invoice line text, e.g. "FSC $0.47/mi (DOE $4.03, week of 2026-09-14)"."""
    week_of = _publication_for(pickup, prices)
    price = _as_decimal(prices[week_of])
    return f"FSC ${surcharge_per_mile(price)}/mi (DOE ${price}, week of {week_of.isoformat()})"
