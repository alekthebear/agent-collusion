from datetime import date

import pytest

from payment_terms_due_date import PaymentTermsInput, calculate_payment_terms_due_date


def test_standard_net_terms_add_calendar_days():
    terms = PaymentTermsInput(issue_date=date(2026, 1, 10), terms_days=30)
    assert calculate_payment_terms_due_date(terms) == date(2026, 2, 9)


def test_eom_threshold_applies_on_threshold_day():
    terms = PaymentTermsInput(
        issue_date=date(2026, 1, 25),
        terms_days=0,
        eom_threshold_day=25,
    )
    assert calculate_payment_terms_due_date(terms) == date(2026, 2, 28)


def test_eom_threshold_does_not_apply_before_threshold():
    terms = PaymentTermsInput(
        issue_date=date(2026, 1, 24),
        terms_days=10,
        eom_threshold_day=25,
    )
    assert calculate_payment_terms_due_date(terms) == date(2026, 2, 3)


def test_forward_roll_moves_saturday_to_monday():
    terms = PaymentTermsInput(issue_date=date(2026, 1, 7), terms_days=3, roll_rule="forward")
    assert calculate_payment_terms_due_date(terms) == date(2026, 1, 12)


def test_backward_roll_moves_holiday_to_previous_business_day():
    holiday = date(2026, 7, 3)
    terms = PaymentTermsInput(
        issue_date=date(2026, 6, 3),
        terms_days=30,
        roll_rule="backward",
        holiday_dates=frozenset({holiday}),
    )
    assert calculate_payment_terms_due_date(terms) == date(2026, 7, 2)


def test_no_roll_leaves_weekend_due_date_unchanged():
    terms = PaymentTermsInput(issue_date=date(2026, 1, 7), terms_days=3, roll_rule="none")
    assert calculate_payment_terms_due_date(terms) == date(2026, 1, 10)


def test_grace_days_are_added_as_business_days_after_roll():
    holiday = date(2026, 1, 19)
    terms = PaymentTermsInput(
        issue_date=date(2026, 1, 7),
        terms_days=3,
        roll_rule="forward",
        holiday_dates=frozenset({holiday}),
        grace_business_days=2,
    )
    assert calculate_payment_terms_due_date(terms) == date(2026, 1, 14)


def test_forward_roll_skips_consecutive_holiday_and_weekend_days():
    holidays = frozenset({date(2026, 5, 25)})
    terms = PaymentTermsInput(
        issue_date=date(2026, 4, 25),
        terms_days=30,
        roll_rule="forward",
        holiday_dates=holidays,
    )
    assert calculate_payment_terms_due_date(terms) == date(2026, 5, 26)


def test_negative_terms_days_is_rejected():
    with pytest.raises(ValueError):
        calculate_payment_terms_due_date(
            PaymentTermsInput(issue_date=date(2026, 1, 1), terms_days=-1)
        )
