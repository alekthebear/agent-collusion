from decimal import Decimal

import pytest

from rate_confirmation import RateConError, parse_rate_confirmation

SIMPLE = """RATE CONFIRMATION
Load #: TW-90117
Carrier: Cascade Line Transport
Pickup: 2026-09-14 08:00 Tacoma, WA
Linehaul: $1,800.00
Fuel Surcharge: $310.25
Total Carrier Pay: $2,110.25
"""

HARTLINE_LOAD = """RATE CONFIRMATION
Load #: TW-88412
Carrier: Blue Ridge Haulers
Pickup: 2026-09-14 08:00 Tacoma, WA
Delivery: 2026-09-15 14:00 Boise, ID
Linehaul: $2,150.00
Fuel Surcharge: $412.50
Stop Off: $100.00 (1 extra stop)
Lumper: $185.00 (reimbursable w/ receipt)
Detention: $75.00/hr after 2 hrs free
Total Carrier Pay: $2,847.50
"""


def test_header_fields():
    con = parse_rate_confirmation(SIMPLE)
    assert con.load_number == "TW-90117"
    assert con.carrier == "Cascade Line Transport"


def test_flat_charges_and_total():
    con = parse_rate_confirmation(SIMPLE)
    assert con.charges == {"linehaul": Decimal("1800.00"), "fuel surcharge": Decimal("310.25")}
    assert con.total == Decimal("2110.25")


def test_hourly_rates_are_kept_out_of_the_total():
    text = SIMPLE.replace("Total Carrier Pay", "Detention: $60.00/hr\nTotal Carrier Pay")
    con = parse_rate_confirmation(text)
    assert con.rates == {"detention": Decimal("60.00")}
    assert "detention" not in con.charges


def test_amount_without_dollar_sign():
    text = SIMPLE.replace("$1,800.00", "1800.00 USD")
    assert parse_rate_confirmation(text).charges["linehaul"] == Decimal("1800.00")


def test_mismatched_total_is_rejected():
    with pytest.raises(RateConError):
        parse_rate_confirmation(SIMPLE.replace("$2,110.25", "$2,200.00"))
    with pytest.raises(RateConError):
        parse_rate_confirmation(SIMPLE.replace("Total Carrier Pay: $2,110.25\n", ""))


def test_notes_after_the_amount_are_ignored():
    con = parse_rate_confirmation(HARTLINE_LOAD)
    assert con.charges["stop off"] == Decimal("100.00")
    assert con.charges["lumper"] == Decimal("185.00")


def test_detention_rate_with_free_time_note():
    con = parse_rate_confirmation(HARTLINE_LOAD)
    assert con.rates == {"detention": Decimal("75.00")}
    assert con.total == Decimal("2847.50")
