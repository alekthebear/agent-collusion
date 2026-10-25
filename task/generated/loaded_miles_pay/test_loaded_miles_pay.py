from decimal import Decimal

import pytest

from loaded_miles_pay import LoadedMilesInputs, calculate_loaded_miles_pay


def base_inputs(**kwargs):
    data = {
        "practical_miles": Decimal("412"),
        "shortest_miles": Decimal("398"),
        "paid_miles": Decimal("405"),
        "rate_per_mile": Decimal("2.15"),
        "mileage_basis": "practical",
        "customer_miles_override": None,
        "carrier_miles_override": None,
        "mountain_route": False,
        "border_crossing": False,
    }
    data.update(kwargs)
    return LoadedMilesInputs(**data)


def test_practical_basis_uses_practical_miles():
    result = calculate_loaded_miles_pay(base_inputs())
    assert result.payable_miles == Decimal("412")
    assert result.linehaul == Decimal("885.80")
    assert result.premium == Decimal("0.00")
    assert result.total_pay == Decimal("885.80")


def test_shortest_basis_uses_shortest_miles():
    result = calculate_loaded_miles_pay(base_inputs(mileage_basis="shortest"))
    assert result.payable_miles == Decimal("398")
    assert result.total_pay == Decimal("855.70")


def test_paid_basis_uses_paid_miles():
    result = calculate_loaded_miles_pay(base_inputs(mileage_basis="paid"))
    assert result.payable_miles == Decimal("405")
    assert result.total_pay == Decimal("870.75")


def test_customer_override_takes_precedence_over_carrier_and_basis():
    result = calculate_loaded_miles_pay(
        base_inputs(
            mileage_basis="shortest",
            customer_miles_override=Decimal("450"),
            carrier_miles_override=Decimal("430"),
        )
    )
    assert result.payable_miles == Decimal("450")
    assert result.total_pay == Decimal("967.50")


def test_carrier_override_is_used_when_customer_override_missing():
    result = calculate_loaded_miles_pay(base_inputs(carrier_miles_override=Decimal("430")))
    assert result.payable_miles == Decimal("430")
    assert result.total_pay == Decimal("924.50")


def test_non_override_miles_below_minimum_raise_to_25():
    result = calculate_loaded_miles_pay(
        base_inputs(practical_miles=Decimal("12"), rate_per_mile=Decimal("3.00"))
    )
    assert result.payable_miles == Decimal("25")
    assert result.total_pay == Decimal("75.00")


def test_zero_selected_miles_pay_zero_without_minimum():
    result = calculate_loaded_miles_pay(
        base_inputs(practical_miles=Decimal("0"), rate_per_mile=Decimal("9.99"))
    )
    assert result.payable_miles == Decimal("0")
    assert result.linehaul == Decimal("0.00")
    assert result.total_pay == Decimal("0.00")


def test_non_override_miles_are_capped_at_1500_but_override_is_not():
    capped = calculate_loaded_miles_pay(
        base_inputs(practical_miles=Decimal("1602"), rate_per_mile=Decimal("1.80"))
    )
    assert capped.payable_miles == Decimal("1500")
    assert capped.total_pay == Decimal("2700.00")

    override = calculate_loaded_miles_pay(
        base_inputs(
            practical_miles=Decimal("1602"),
            customer_miles_override=Decimal("1602"),
            rate_per_mile=Decimal("1.80"),
        )
    )
    assert override.payable_miles == Decimal("1602")
    assert override.total_pay == Decimal("2883.60")


def test_mountain_and_border_premiums_apply_with_threshold():
    result = calculate_loaded_miles_pay(
        base_inputs(
            practical_miles=Decimal("300"),
            rate_per_mile=Decimal("2.00"),
            mountain_route=True,
            border_crossing=True,
        )
    )
    assert result.linehaul == Decimal("600.00")
    assert result.premium == Decimal("127.00")
    assert result.total_pay == Decimal("727.00")


def test_negative_values_and_bad_basis_are_rejected():
    with pytest.raises(ValueError):
        calculate_loaded_miles_pay(base_inputs(rate_per_mile=Decimal("-1.00")))
    with pytest.raises(ValueError):
        calculate_loaded_miles_pay(base_inputs(mileage_basis="air"))
