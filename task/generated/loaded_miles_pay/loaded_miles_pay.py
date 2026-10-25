"""Loaded-miles linehaul pay for one shipment leg.

Tidewater settles many spot and contract loads from a per-loaded-mile rate. The
payable miles are not always the raw dispatch miles: some customers pay practical
miles from the routing guide, some contracts pay shortest miles, and some legacy
accounts use an agreed paid-mile figure. A customer-specific override takes
precedence over a carrier-provided one because billing must follow the customer
contract first.

Business rules used by settlement:
- Use the miles selected by the requested basis: practical, shortest, or paid.
- If ``customer_miles_override`` is present, use it regardless of basis.
- Else if ``carrier_miles_override`` is present, use it regardless of basis.
- Negative miles or rates are invalid.
- Loaded miles under 25 are raised to a 25-mile minimum for pay.
- If loaded miles exceed 1,500, cap payable miles at 1,500 unless an override was
  used; agreed overrides are honored as entered.
- If the selected non-override miles are zero, pay is zero; the 25-mile minimum does
  not create pay on a canceled or non-moved leg.
- Add a 7% mountain premium when ``mountain_route`` is true and payable miles are at
  least 300.
- Add a flat border-crossing premium of $85.00 when ``border_crossing`` is true.
- Final pay is rounded to cents using half-up rounding.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
MINIMUM_MILES = Decimal("25")
MAX_NON_OVERRIDE_MILES = Decimal("1500")
BORDER_PREMIUM = Decimal("85.00")
MOUNTAIN_PREMIUM_RATE = Decimal("0.07")


@dataclass(frozen=True)
class LoadedMilesInputs:
    practical_miles: Decimal
    shortest_miles: Decimal
    paid_miles: Decimal
    rate_per_mile: Decimal
    mileage_basis: str = "practical"
    customer_miles_override: Decimal | None = None
    carrier_miles_override: Decimal | None = None
    mountain_route: bool = False
    border_crossing: bool = False


@dataclass(frozen=True)
class LoadedMilesPay:
    payable_miles: Decimal
    linehaul: Decimal
    premium: Decimal
    total_pay: Decimal


def _validate(inputs: LoadedMilesInputs) -> None:
    if inputs.mileage_basis not in {"practical", "shortest", "paid"}:
        raise ValueError(f"unsupported mileage_basis {inputs.mileage_basis!r}")
    values = {
        "practical_miles": inputs.practical_miles,
        "shortest_miles": inputs.shortest_miles,
        "paid_miles": inputs.paid_miles,
        "rate_per_mile": inputs.rate_per_mile,
        "customer_miles_override": inputs.customer_miles_override,
        "carrier_miles_override": inputs.carrier_miles_override,
    }
    for name, value in values.items():
        if value is not None and value < 0:
            raise ValueError(f"{name} cannot be negative: {value}")


def _selected_miles(inputs: LoadedMilesInputs) -> tuple[Decimal, bool]:
    if inputs.customer_miles_override is not None:
        return inputs.customer_miles_override, True
    if inputs.carrier_miles_override is not None:
        return inputs.carrier_miles_override, True
    if inputs.mileage_basis == "practical":
        return inputs.practical_miles, False
    if inputs.mileage_basis == "shortest":
        return inputs.shortest_miles, False
    return inputs.paid_miles, False


def _payable_miles(raw_miles: Decimal, from_override: bool) -> Decimal:
    if raw_miles == 0:
        return Decimal("0")
    if from_override:
        return raw_miles
    miles = raw_miles
    if miles < MINIMUM_MILES:
        miles = MINIMUM_MILES
    if miles > MAX_NON_OVERRIDE_MILES:
        miles = MAX_NON_OVERRIDE_MILES
    return miles


def _premium(payable_miles: Decimal, linehaul: Decimal, inputs: LoadedMilesInputs) -> Decimal:
    premium = Decimal("0.00")
    if inputs.mountain_route and payable_miles >= Decimal("300"):
        premium += linehaul * MOUNTAIN_PREMIUM_RATE
    if inputs.border_crossing:
        premium += BORDER_PREMIUM
    return premium.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_loaded_miles_pay(inputs: LoadedMilesInputs) -> LoadedMilesPay:
    """Compute loaded-miles pay for a shipment leg.

    The selected mileage basis supplies miles unless a customer or carrier override
    is present. Non-override miles are subject to a 25-mile minimum and a 1,500-mile
    cap. Premiums are added after the base linehaul is calculated.
    """
    _validate(inputs)
    raw_miles, from_override = _selected_miles(inputs)
    payable_miles = _payable_miles(raw_miles, from_override)
    linehaul = (payable_miles * inputs.rate_per_mile).quantize(CENT, rounding=ROUND_HALF_UP)
    premium = _premium(payable_miles, linehaul, inputs)
    total_pay = (linehaul + premium).quantize(CENT, rounding=ROUND_HALF_UP)
    return LoadedMilesPay(
        payable_miles=payable_miles,
        linehaul=linehaul,
        premium=premium,
        total_pay=total_pay,
    )
