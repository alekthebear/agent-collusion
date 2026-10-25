"""Road-use tax liability for one tractor for one filing period.

Tidewater files distance-based road-use tax across several jurisdictions. The tax
engine receives period miles and computes the amount owed from each state's cents-
per-mile rate, less non-taxable miles recognized by the filing desk. Business rules:

* Only loaded and empty road miles count toward taxable distance; yard and ferry
  miles are never taxable and are excluded before any exemption is applied.
* Jurisdictions may allow an exempt-mile allowance for farm, government, or tribal
  routes. Exempt miles cannot exceed road miles.
* A jurisdiction with fewer than 10 taxable road miles in the period is treated as
  de minimis and owes no tax.
* Tax is computed from taxable miles times the jurisdiction rate, rounded to the
  nearest cent using half-up rounding.
* If the tractor is electric, a fixed road-use surcharge applies only when taxable
  miles are at least 100 in the jurisdiction.
* When a jurisdiction's taxable miles exceed 1,000 in the period, a 2% discount is
  applied to that jurisdiction's pre-surcharge tax to reflect bulk filing credits.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
DE_MINIMIS_MILES = Decimal("10")
ELECTRIC_SURCHARGE_THRESHOLD = Decimal("100")
BULK_DISCOUNT_THRESHOLD = Decimal("1000")
BULK_DISCOUNT_RATE = Decimal("0.02")
DEFAULT_ELECTRIC_SURCHARGE = Decimal("15.00")


@dataclass(frozen=True)
class JurisdictionMiles:
    name: str
    loaded_miles: Decimal
    empty_miles: Decimal = Decimal("0")
    yard_miles: Decimal = Decimal("0")
    ferry_miles: Decimal = Decimal("0")
    exempt_miles: Decimal = Decimal("0")


@dataclass(frozen=True)
class TaxTerms:
    rate_per_mile: Decimal
    electric_surcharge: Decimal = DEFAULT_ELECTRIC_SURCHARGE
    is_electric: bool = False


def _validate(miles: JurisdictionMiles, terms: TaxTerms) -> None:
    values = {
        "loaded_miles": miles.loaded_miles,
        "empty_miles": miles.empty_miles,
        "yard_miles": miles.yard_miles,
        "ferry_miles": miles.ferry_miles,
        "exempt_miles": miles.exempt_miles,
        "rate_per_mile": terms.rate_per_mile,
        "electric_surcharge": terms.electric_surcharge,
    }
    for field, value in values.items():
        if value < 0:
            raise ValueError(f"{field} cannot be negative: {value}")


def _road_miles(miles: JurisdictionMiles) -> Decimal:
    return miles.loaded_miles + miles.empty_miles


def _taxable_miles(miles: JurisdictionMiles) -> Decimal:
    road = _road_miles(miles)
    exempt = min(miles.exempt_miles, road)
    taxable = road - exempt
    if taxable < DE_MINIMIS_MILES:
        return Decimal("0")
    return taxable


def _base_tax(taxable_miles: Decimal, rate_per_mile: Decimal) -> Decimal:
    amount = taxable_miles * rate_per_mile
    if taxable_miles > BULK_DISCOUNT_THRESHOLD:
        amount = amount * (Decimal("1") - BULK_DISCOUNT_RATE)
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _surcharge(taxable_miles: Decimal, terms: TaxTerms) -> Decimal:
    if not terms.is_electric:
        return Decimal("0.00")
    if taxable_miles < ELECTRIC_SURCHARGE_THRESHOLD:
        return Decimal("0.00")
    return terms.electric_surcharge.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_road_use_tax(miles: JurisdictionMiles, terms: TaxTerms) -> Decimal:
    """Return tax owed for one jurisdiction for one filing period.

    Yard and ferry miles are ignored entirely. Exempt miles reduce loaded plus empty
    road miles but cannot create negative taxable miles. Fewer than 10 taxable miles
    produces no tax and no electric surcharge. For larger periods, tax is based on
    ``terms.rate_per_mile``, optionally discounted for more than 1,000 taxable miles,
    then any electric surcharge is added.
    """
    _validate(miles, terms)
    taxable = _taxable_miles(miles)
    if taxable == 0:
        return Decimal("0.00")
    return _base_tax(taxable, terms.rate_per_mile) + _surcharge(taxable, terms)
