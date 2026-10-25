from decimal import Decimal

import pytest

from minimum_charge import apply_minimum, lane_type, minimum_for


def test_lane_type_by_miles_and_states():
    assert lane_type("WA", "WA", Decimal("32")) == "local"
    assert lane_type("WA", "WA", Decimal("50")) == "intrastate"
    assert lane_type("WA", "OR", Decimal("12")) == "interstate"


def test_default_minimums_for_customer_without_a_contract():
    assert minimum_for("ACME", "local") == Decimal("275.00")
    assert minimum_for("ACME", "intrastate") == Decimal("450.00")


def test_hartline_contract_minimums():
    assert minimum_for("HARTLINE", "local") == Decimal("225.00")
    assert minimum_for("HARTLINE", "interstate") == Decimal("575.00")


def test_linehaul_above_the_minimum_is_unchanged():
    assert apply_minimum("HARTLINE", "WA", "OR", Decimal("180"), Decimal("612.40")) == Decimal("612.40")


def test_unknown_lane_type_is_rejected():
    with pytest.raises(ValueError):
        minimum_for("HARTLINE", "regional")


def test_hartline_intrastate_minimum():
    assert minimum_for("HARTLINE", "intrastate") == Decimal("325.00")


def test_tacoma_to_yakima_bills_the_contract_minimum():
    # Load TW-90544: 150 miles at $2.05 a mile, under the intrastate minimum.
    assert apply_minimum("HARTLINE", "WA", "WA", Decimal("150"), Decimal("307.50")) == Decimal("325.00")
