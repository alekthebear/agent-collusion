from datetime import date
from decimal import Decimal

import pytest

from bad_debt_reserve import Receivable, calculate_bad_debt_reserve


def test_current_standard_invoice_uses_lowest_bucket():
    rec = Receivable(date(2026, 1, 1), date(2026, 1, 31), Decimal("1000.00"))
    assert calculate_bad_debt_reserve(rec) == Decimal("5.00")


def test_future_dated_invoice_is_treated_as_current():
    rec = Receivable(date(2026, 2, 10), date(2026, 2, 1), Decimal("1000.00"))
    assert calculate_bad_debt_reserve(rec) == Decimal("5.00")


def test_31st_day_moves_to_next_bucket():
    rec = Receivable(date(2026, 1, 1), date(2026, 2, 1), Decimal("1000.00"))
    assert calculate_bad_debt_reserve(rec) == Decimal("20.00")


def test_low_risk_multiplier_and_half_up_rounding_apply():
    rec = Receivable(date(2026, 1, 1), date(2026, 4, 1), Decimal("333.00"), risk_class="low")
    assert calculate_bad_debt_reserve(rec) == Decimal("17.48")


def test_dispute_adds_surcharge_only_after_30_days():
    rec = Receivable(
        date(2026, 1, 1), date(2026, 2, 15), Decimal("1000.00"), in_dispute=True
    )
    assert calculate_bad_debt_reserve(rec) == Decimal("120.00")


def test_current_invoice_caps_recovery_at_80_percent():
    rec = Receivable(
        date(2026, 1, 1), date(2026, 1, 20), Decimal("1000.00"), recovery_rate=Decimal("0.90")
    )
    assert calculate_bad_debt_reserve(rec) == Decimal("1.00")


def test_letter_of_credit_reserves_zero():
    rec = Receivable(
        date(2026, 1, 1), date(2026, 6, 1), Decimal("1000.00"), secured_by_letter_of_credit=True
    )
    assert calculate_bad_debt_reserve(rec) == Decimal("0.00")


def test_small_balance_gets_minimum_floor_when_positive():
    rec = Receivable(date(2026, 1, 1), date(2026, 1, 31), Decimal("40.00"))
    assert calculate_bad_debt_reserve(rec) == Decimal("1.00")


def test_negative_balance_is_zero_reserve():
    rec = Receivable(date(2026, 1, 1), date(2026, 5, 1), Decimal("-25.00"))
    assert calculate_bad_debt_reserve(rec) == Decimal("0.00")


def test_invalid_recovery_rate_is_rejected():
    rec = Receivable(
        date(2026, 1, 1), date(2026, 5, 1), Decimal("100.00"), recovery_rate=Decimal("1.10")
    )
    with pytest.raises(ValueError):
        calculate_bad_debt_reserve(rec)
