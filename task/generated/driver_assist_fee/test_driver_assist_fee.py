from decimal import Decimal

import pytest

from driver_assist_fee import AssistStop, DriverAssistTerms, calculate_driver_assist_fee


def test_no_assist_required_is_free():
    stop = AssistStop(pieces=80, weight_lb=4000, assist_minutes=90, assist_required=False)
    assert calculate_driver_assist_fee(stop) == Decimal("0.00")


def test_piece_billing_charges_only_above_included_threshold():
    stop = AssistStop(pieces=30, assist_required=True)
    assert calculate_driver_assist_fee(stop) == Decimal("35.00")


def test_piece_billing_exact_threshold_has_no_charge():
    stop = AssistStop(pieces=24, assist_required=True)
    assert calculate_driver_assist_fee(stop) == Decimal("0.00")


def test_weight_billing_uses_started_500_lb_increments():
    stop = AssistStop(weight_lb=1601, assist_required=True)
    terms = DriverAssistTerms(billing_basis="weight")
    assert calculate_driver_assist_fee(stop, terms) == Decimal("35.00")


def test_time_billing_uses_started_15_minute_increments():
    stop = AssistStop(assist_minutes=46, assist_required=True)
    terms = DriverAssistTerms(billing_basis="time")
    assert calculate_driver_assist_fee(stop, terms) == Decimal("35.00")


def test_flat_fee_billing_ignores_counts_and_time():
    stop = AssistStop(pieces=1, weight_lb=1, assist_minutes=1, assist_required=True)
    terms = DriverAssistTerms(billing_basis="flat", flat_fee=Decimal("72.25"))
    assert calculate_driver_assist_fee(stop, terms) == Decimal("72.25")


def test_residential_surcharge_is_added_before_bounds():
    stop = AssistStop(pieces=25, assist_required=True, residential=True)
    assert calculate_driver_assist_fee(stop) == Decimal("35.00")


def test_reefer_under_2000_lb_is_waived_even_if_assist_required():
    stop = AssistStop(weight_lb=1999, assist_required=True, reefer=True)
    terms = DriverAssistTerms(billing_basis="weight")
    assert calculate_driver_assist_fee(stop, terms) == Decimal("0.00")


def test_maximum_charge_caps_large_time_based_fee():
    stop = AssistStop(assist_minutes=600, assist_required=True, residential=True)
    terms = DriverAssistTerms(billing_basis="time")
    assert calculate_driver_assist_fee(stop, terms) == Decimal("250.00")


def test_negative_inputs_are_rejected():
    with pytest.raises(ValueError):
        calculate_driver_assist_fee(AssistStop(pieces=-1, assist_required=True))
