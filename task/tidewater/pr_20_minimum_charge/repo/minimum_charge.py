"""Minimum linehaul charges by lane type.

Short moves cost a carrier nearly as much as long ones (the truck still has to get
there and back), so customer contracts set a minimum linehaul charge. The minimum
depends on the lane type:

    local       under 50 miles
    intrastate  50 miles or more, origin and destination in the same state
    interstate  origin and destination in different states

Minimums live in ``pricing/minimum_charges.json``, which Pricing loads from each
customer's contract. A customer's own minimum wins; a lane type their contract does
not list uses the default. Rating calls ``apply_minimum`` after it prices linehaul
from the lane rate.
"""

import json
from decimal import Decimal
from pathlib import Path

MINIMUMS_FILE = Path(__file__).parent / "pricing" / "minimum_charges.json"
LANE_TYPES = ("local", "intrastate", "interstate")
LOCAL_MILES = Decimal("50")


def _load(path: Path = MINIMUMS_FILE) -> dict:
    with open(path) as handle:
        return json.load(handle)


def lane_type(origin_state: str, dest_state: str, miles: Decimal) -> str:
    if miles < 0:
        raise ValueError(f"negative miles {miles}")
    if origin_state.upper() != dest_state.upper():
        return "interstate"
    return "local" if miles < LOCAL_MILES else "intrastate"


def minimum_for(customer: str, kind: str) -> Decimal:
    """The minimum linehaul charge ``customer`` pays on a lane of type ``kind``."""
    if kind not in LANE_TYPES:
        raise ValueError(f"unknown lane type {kind!r}")
    data = _load()
    contract = data["customers"].get(customer.upper(), {})
    return Decimal(contract.get(kind, data["default"][kind]))


def apply_minimum(
    customer: str, origin_state: str, dest_state: str, miles: Decimal, linehaul: Decimal
) -> Decimal:
    """Linehaul raised to the customer's minimum for this lane, if it falls short."""
    minimum = minimum_for(customer, lane_type(origin_state, dest_state, miles))
    return max(linehaul, minimum)
