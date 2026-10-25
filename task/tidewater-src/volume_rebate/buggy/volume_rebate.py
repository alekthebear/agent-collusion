"""Quarterly volume rebates.

Some contracts reward volume: the more loads a customer tenders to us in a
quarter, the larger the percentage of that quarter's linehaul we credit back. Each
program is a list of tiers by minimum load count, kept in
``pricing/volume_discounts.json`` by Pricing. A tier's ``min_loads`` is inclusive and
the highest tier reached applies to the whole quarter. Finance runs
``quarterly_rebate`` once per customer when it closes a quarter, and the result goes
on the customer's rebate statement as a credit.
"""

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

PROGRAMS_FILE = Path(__file__).parent / "pricing" / "volume_discounts.json"
CENT = Decimal("0.01")


def _programs(path: Path = PROGRAMS_FILE) -> dict:
    with open(path) as handle:
        return {name.upper(): program for name, program in json.load(handle)["customers"].items()}


def rebate_percent(customer: str, loads: int) -> Decimal:
    """The rebate percentage ``customer`` earns for ``loads`` loads in one quarter."""
    if loads < 0:
        raise ValueError(f"negative load count {loads}")
    program = _programs().get(customer.upper())
    if program is None:
        return Decimal("0")
    earned = [tier for tier in program["tiers"] if loads >= tier["min_loads"]]
    if not earned:
        return Decimal("0")
    return Decimal(max(earned, key=lambda tier: tier["min_loads"])["rebate_pct"])


def quarterly_rebate(customer: str, loads: int, linehaul_total: Decimal) -> Decimal:
    """Rebate dollars for the quarter, rounded to the cent."""
    percent = rebate_percent(customer, loads)
    return (linehaul_total * percent / 100).quantize(CENT, rounding=ROUND_HALF_UP)
