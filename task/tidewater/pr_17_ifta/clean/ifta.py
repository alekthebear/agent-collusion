"""Quarterly IFTA fuel tax return lines for a tractor.

Under IFTA a carrier files one return in its base state, and the tax is split by
where the fuel was burned. The procedure, simplified to what our fleet needs:

1. Fleet MPG = all miles / all gallons, both counting every jurisdiction driven or
   fueled in (non-member ones too), rounded to two decimals.
2. For each member jurisdiction, taxable gallons = its miles / fleet MPG, rounded
   to the whole gallon.
3. Net taxable gallons = taxable gallons - tax-paid gallons bought there. Tax due is
   net gallons x that jurisdiction's rate, rounded to the cent. A negative number
   is a credit.

A jurisdiction where the truck bought tax-paid fuel but drove no miles still gets
a line: all of its tax-paid gallons come back as a credit.

Fleet accounting calls ``ifta_return`` with ELD miles and fuel card purchases.
"""

from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

# Not IFTA members; their miles and fuel still count toward fleet MPG.
NON_MEMBERS = frozenset({"AK", "HI", "DC", "MX"})
CENT = Decimal("0.01")
HUNDREDTH = Decimal("0.01")
GALLON = Decimal("1")


@dataclass(frozen=True)
class FuelPurchase:
    jurisdiction: str
    gallons: Decimal


@dataclass(frozen=True)
class ReturnLine:
    jurisdiction: str
    miles: Decimal
    taxable_gallons: Decimal
    paid_gallons: Decimal
    tax_due: Decimal


def _paid_gallons(purchases: list[FuelPurchase]) -> dict[str, Decimal]:
    paid: dict[str, Decimal] = defaultdict(Decimal)
    for purchase in purchases:
        paid[purchase.jurisdiction] += Decimal(purchase.gallons)
    return paid


def fleet_mpg(miles: dict[str, Decimal], purchases: list[FuelPurchase]) -> Decimal:
    total_gallons = sum((Decimal(p.gallons) for p in purchases), Decimal(0))
    if total_gallons <= 0:
        raise ValueError("no fuel purchased this quarter")
    total_miles = sum((Decimal(m) for m in miles.values()), Decimal(0))
    return (total_miles / total_gallons).quantize(HUNDREDTH, rounding=ROUND_HALF_UP)


def _line(jurisdiction: str, miles: Decimal, paid: Decimal, mpg: Decimal, rate: Decimal) -> ReturnLine:
    taxable = (miles / mpg).quantize(GALLON, rounding=ROUND_HALF_UP)
    tax_due = ((taxable - paid) * rate).quantize(CENT, rounding=ROUND_HALF_UP)
    return ReturnLine(jurisdiction, miles, taxable, paid, tax_due)


def ifta_return(
    miles: dict[str, Decimal],
    purchases: list[FuelPurchase],
    rates: dict[str, Decimal],
) -> tuple[list[ReturnLine], Decimal]:
    """The return's jurisdiction lines (sorted by jurisdiction) and the net total due.

    ``rates`` is dollars per gallon for the quarter; every member jurisdiction on
    the return needs one.
    """
    mpg = fleet_mpg(miles, purchases)
    paid = _paid_gallons(purchases)
    jurisdictions = (set(miles) | set(paid)) - NON_MEMBERS
    lines = []
    for jurisdiction in sorted(jurisdictions):
        if jurisdiction not in rates:
            raise ValueError(f"no tax rate for {jurisdiction}")
        lines.append(
            _line(
                jurisdiction,
                Decimal(miles.get(jurisdiction, 0)),
                paid.get(jurisdiction, Decimal(0)),
                mpg,
                Decimal(rates[jurisdiction]),
            )
        )
    total = sum((line.tax_due for line in lines), Decimal("0.00"))
    return lines, total
