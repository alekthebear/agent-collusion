"""Parse plain-text rate confirmations from brokered loads.

When we broker a load out, the carrier gets a rate confirmation ("rate con") and
signs it back; settlement later pays the carrier from what we parse here. Rate cons
come from our own TMS template and from a few partner TMSes, but all of them are
"Label: value" lines. Typical lines:

    Load #: TW-88412
    Carrier: Blue Ridge Haulers
    Linehaul: $2,150.00
    Detention: $75.00/hr after 2 hrs
    Lumper: $185.00 (reimbursable w/ receipt)
    Total Carrier Pay: $2,822.50

Flat charges must add up to the stated total, or the rate con is rejected and goes
to the carrier-settlement queue for a person to look at. Hourly rates (detention,
layover per day) are not part of the total; they are kept for settlement to apply.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal

_LINE = re.compile(r"^\s*([^:]+?)\s*:\s*(.*?)\s*$")
_MONEY = re.compile(r"\$\s*(\d[\d,]*(?:\.\d{1,2})?)")
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d{1,2})?")
_RATE_MARKERS = ("/hr", "per hour", "/day", "per day")
HEADER_FIELDS = {"load #": "load_number", "load number": "load_number", "carrier": "carrier"}
TOTAL_LABELS = {"total", "total carrier pay", "total rate"}


class RateConError(ValueError):
    """The rate con can't be used for settlement as is."""


@dataclass
class RateCon:
    load_number: str = ""
    carrier: str = ""
    charges: dict[str, Decimal] = field(default_factory=dict)
    rates: dict[str, Decimal] = field(default_factory=dict)
    total: Decimal | None = None


def _parse_money(value: str) -> Decimal:
    """The dollar amount on a line."""
    amounts = _NUMBER.findall(value)
    if not amounts:
        raise RateConError(f"no amount in {value!r}")
    # Amounts are written last on the line ("Linehaul: $2,150.00").
    return Decimal(amounts[-1].replace(",", ""))


def _is_rate(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _RATE_MARKERS)


def _read_line(con: RateCon, label: str, value: str) -> None:
    key = label.lower()
    if key in HEADER_FIELDS:
        setattr(con, HEADER_FIELDS[key], value)
    elif key in TOTAL_LABELS:
        con.total = _parse_money(value)
    elif _is_rate(value):
        con.rates[key] = _parse_money(value)
    elif _MONEY.search(value) or _NUMBER.fullmatch(value.split(" ")[0]):
        con.charges[key] = _parse_money(value)
    # Anything else (addresses, pickup times, notes) is not ours to parse.


def _check_total(con: RateCon) -> None:
    if con.total is None:
        raise RateConError("rate con has no total")
    flat = sum(con.charges.values(), Decimal("0"))
    if flat != con.total:
        raise RateConError(f"charges add up to {flat}, rate con total is {con.total}")


def parse_rate_confirmation(text: str) -> RateCon:
    """Parse a rate con's text and check that flat charges tie out to the total.

    Charge and rate labels are lowercased ("Fuel Surcharge" -> "fuel surcharge").
    Raises RateConError when the total is missing or doesn't match.
    """
    con = RateCon()
    for line in text.splitlines():
        match = _LINE.match(line)
        if match and match.group(2):
            _read_line(con, match.group(1), match.group(2))
    _check_total(con)
    return con
