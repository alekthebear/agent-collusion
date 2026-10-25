"""Accessorial charge lookup for customer invoices.

Accessorials are the per-stop extras billed on top of linehaul: liftgate, inside
delivery, residential delivery, delivery appointments and the like. The rates live
in ``pricing/accessorial_rates.json``, which Pricing loads from each customer's
contract. A customer's own rate wins; any code their contract does not list bills
at the default rate. The billing service calls ``accessorial_total`` once per load
with the codes dispatch recorded on its stops.
"""

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

RATES_FILE = Path(__file__).parent / "pricing" / "accessorial_rates.json"
CENT = Decimal("0.01")


def load_rates(path: Path = RATES_FILE) -> dict:
    """The rate file as read from disk, with every amount parsed as Decimal."""
    with open(path) as handle:
        data = json.load(handle)
    return {
        "default": {code: Decimal(amount) for code, amount in data["default"].items()},
        "customers": {
            customer.upper(): {code: Decimal(amount) for code, amount in rates.items()}
            for customer, rates in data["customers"].items()
        },
    }


def accessorial_rate(customer: str, code: str, rates: dict | None = None) -> Decimal:
    """The per-occurrence rate ``customer`` pays for accessorial ``code``.

    Raises LookupError for a code that has no default rate.
    """
    rates = rates or load_rates()
    code = code.upper()
    if code not in rates["default"]:
        raise LookupError(f"unknown accessorial code {code!r}")
    contract = rates["customers"].get(customer.upper(), {})
    return contract.get(code, rates["default"][code]).quantize(CENT, rounding=ROUND_HALF_UP)


def accessorial_total(customer: str, codes: list[str]) -> Decimal:
    """Total accessorials for one load: one charge per code occurrence."""
    rates = load_rates()
    total = sum((accessorial_rate(customer, code, rates) for code in codes), Decimal("0.00"))
    return total.quantize(CENT, rounding=ROUND_HALF_UP)
