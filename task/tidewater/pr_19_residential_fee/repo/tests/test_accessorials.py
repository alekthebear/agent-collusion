from decimal import Decimal

import pytest

from accessorials import accessorial_rate, accessorial_total


def test_default_rate_for_customer_without_a_contract():
    assert accessorial_rate("ACME", "LIFTGATE") == Decimal("85.00")


def test_contract_rate_wins_over_default():
    assert accessorial_rate("HARTLINE", "LIFTGATE") == Decimal("65.00")
    assert accessorial_rate("BRIGHTWATER", "LIMITED_ACCESS") == Decimal("80.00")


def test_unlisted_code_falls_back_to_default():
    assert accessorial_rate("HARTLINE", "APPOINTMENT") == Decimal("35.00")


def test_customer_and_code_are_case_insensitive():
    assert accessorial_rate("hartline", "liftgate") == Decimal("65.00")


def test_unknown_code_is_rejected():
    with pytest.raises(LookupError):
        accessorial_rate("HARTLINE", "PALLET_JACK")


def test_hartline_residential_delivery_rate():
    assert accessorial_rate("HARTLINE", "RESIDENTIAL") == Decimal("59.00")


def test_hartline_store_direct_load_total():
    # Load TW-90317: two residential stops and a liftgate at the second.
    codes = ["RESIDENTIAL", "RESIDENTIAL", "LIFTGATE"]
    assert accessorial_total("HARTLINE", codes) == Decimal("183.00")
