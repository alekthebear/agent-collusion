from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from layover_pay import LayoverTerms, LayoverWindow, calculate_layover_pay


def at(day, hour, minute=0):
    return datetime(2026, 3, day, hour, minute)


def test_less_than_24_hours_pays_nothing():
    window = LayoverWindow(available_at=at(2, 8), next_appointment=at(3, 7, 59))
    pay = calculate_layover_pay(window)
    assert pay.payable_days == 0
    assert pay.amount == Decimal("0.00")


def test_exactly_24_hours_pays_one_day():
    window = LayoverWindow(available_at=at(2, 8), next_appointment=at(3, 8))
    pay = calculate_layover_pay(window)
    assert pay.payable_days == 1
    assert pay.amount == Decimal("250.00")


def test_full_48_hours_pays_two_days():
    window = LayoverWindow(available_at=at(2, 9), next_appointment=at(4, 9))
    pay = calculate_layover_pay(window)
    assert pay.payable_days == 2
    assert pay.amount == Decimal("500.00")


def test_partial_second_day_does_not_create_extra_day():
    window = LayoverWindow(available_at=at(2, 8), next_appointment=at(4, 7, 59))
    pay = calculate_layover_pay(window)
    assert pay.payable_days == 1
    assert pay.amount == Decimal("250.00")


def test_same_day_reset_blocks_payment():
    window = LayoverWindow(available_at=at(2, 0, 5), next_appointment=at(2, 23, 55))
    pay = calculate_layover_pay(window)
    assert pay.payable_days == 0
    assert pay.amount == Decimal("0.00")


def test_not_tractor_ready_pays_half_rate():
    window = LayoverWindow(
        available_at=at(2, 8), next_appointment=at(3, 8), tractor_ready=False
    )
    pay = calculate_layover_pay(window)
    assert pay.payable_days == 1
    assert pay.amount == Decimal("125.00")


def test_customer_cancelled_event_never_pays():
    window = LayoverWindow(
        available_at=at(2, 8), next_appointment=at(4, 8), customer_cancelled=True
    )
    pay = calculate_layover_pay(window)
    assert pay.payable_days == 0
    assert pay.amount == Decimal("0.00")


def test_contract_cap_limits_amount_but_not_units():
    window = LayoverWindow(available_at=at(2, 8), next_appointment=at(5, 8))
    terms = LayoverTerms(event_cap=Decimal("600.00"), max_days=None)
    pay = calculate_layover_pay(window, terms)
    assert pay.payable_days == 3
    assert pay.amount == Decimal("600.00")


def test_departure_before_available_is_rejected():
    with pytest.raises(ValueError):
        calculate_layover_pay(
            LayoverWindow(available_at=at(3, 8), next_appointment=at(2, 8))
        )


def test_max_days_limit_applies_before_amount():
    window = LayoverWindow(available_at=at(2, 8), next_appointment=at(6, 8))
    terms = LayoverTerms(max_days=2, event_cap=None)
    pay = calculate_layover_pay(window, terms)
    assert pay.payable_days == 2
    assert pay.amount == Decimal("500.00")
