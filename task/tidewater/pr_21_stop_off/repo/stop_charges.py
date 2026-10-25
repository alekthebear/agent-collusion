"""Stop-off charges for multi-stop truckload moves.

A multi-stop load picks up at the origin, makes one or more intermediate stops,
and ends at a final destination. Carriers bill each intermediate stop as a
stop-off. Customer contracts can include some free stops, set the per-stop rate,
and cap how many stops are billed on one load. The terms live in
``pricing/stop_charges.json``, which Pricing loads from each contract; a customer's
terms override the defaults field by field. Settlement calls ``stop_off_charge``
once per load.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

STOP_TERMS_FILE = Path(__file__).parent / "pricing" / "stop_charges.json"


@dataclass(frozen=True)
class StopTerms:
    free_stops: int
    per_stop: Decimal
    max_billed_stops: int | None


def stop_terms(customer: str, path: Path = STOP_TERMS_FILE) -> StopTerms:
    """``customer``'s stop-off terms: their contract over the defaults."""
    with open(path) as handle:
        data = json.load(handle)
    merged = {**data["default"], **data["customers"].get(customer.upper(), {})}
    return StopTerms(
        free_stops=int(merged["free_stops"]),
        per_stop=Decimal(merged["per_stop"]),
        max_billed_stops=merged["max_billed_stops"],
    )


def billed_stops(intermediate_stops: int, terms: StopTerms) -> int:
    """Intermediate stops billed after the free stops, capped by the contract."""
    if intermediate_stops < 0:
        raise ValueError(f"negative stop count {intermediate_stops}")
    billed = max(0, intermediate_stops - terms.free_stops)
    if terms.max_billed_stops is not None:
        billed = min(billed, terms.max_billed_stops)
    return billed


def stop_off_charge(customer: str, intermediate_stops: int) -> Decimal:
    """Stop-off dollars for one load with ``intermediate_stops`` stops between origin and destination."""
    terms = stop_terms(customer)
    return (terms.per_stop * billed_stops(intermediate_stops, terms)).quantize(Decimal("0.01"))
