from decimal import Decimal

import pytest

from stop_charges import stop_off_charge


def test_direct_load_has_no_stop_charge():
    assert stop_off_charge("ACME", 0) == Decimal("0.00")


def test_default_terms_bill_every_stop():
    assert stop_off_charge("ACME", 3) == Decimal("225.00")


def test_default_terms_cap_billed_stops():
    assert stop_off_charge("ACME", 9) == Decimal("450.00")


def test_uncapped_contract_bills_every_stop():
    assert stop_off_charge("BRIGHTWATER", 9) == Decimal("630.00")


def test_hartline_single_stop_is_free():
    assert stop_off_charge("HARTLINE", 1) == Decimal("0.00")


def test_negative_stop_count_is_rejected():
    with pytest.raises(ValueError):
        stop_off_charge("HARTLINE", -1)


def test_hartline_second_stop_is_free():
    assert stop_off_charge("HARTLINE", 2) == Decimal("0.00")


def test_hartline_store_run_with_three_stops():
    # Load TW-91022: Tacoma DC, three store stops, final stop at Olympia.
    assert stop_off_charge("HARTLINE", 3) == Decimal("60.00")
