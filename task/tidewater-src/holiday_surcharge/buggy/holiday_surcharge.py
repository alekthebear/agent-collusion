"""Holiday surcharge on truckload quotes.

Drivers who run on a holiday are paid a holiday premium, and capacity is thin, so
loads that pick up on a company holiday carry a surcharge: a percentage of
linehaul. The holiday calendar and the percentage live in
``pricing/holiday_calendar.json``, which Pricing publishes each December for the
year ahead. Only the dates on that calendar are surcharged; a holiday that falls on
a weekend is listed on its observed weekday. Quoting calls ``holiday_surcharge`` for
every truckload quote.
"""

import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

CALENDAR_FILE = Path(__file__).parent / "pricing" / "holiday_calendar.json"
CENT = Decimal("0.01")


def _calendar(path: Path = CALENDAR_FILE) -> dict:
    with open(path) as handle:
        return json.load(handle)


def holidays() -> dict[date, str]:
    """Surcharged dates and their names."""
    return {date.fromisoformat(entry["date"]): entry["name"] for entry in _calendar()["holidays"]}


def holiday_name(day: date) -> str | None:
    return holidays().get(day)


def is_holiday(day: date) -> bool:
    return day in holidays()


def holiday_surcharge(pickup: date, linehaul: Decimal) -> Decimal:
    """Surcharge for a load picking up on ``pickup``, rounded to the cent."""
    if not is_holiday(pickup):
        return Decimal("0.00")
    percent = Decimal(_calendar()["surcharge_pct"])
    return (linehaul * percent / 100).quantize(CENT, rounding=ROUND_HALF_UP)
