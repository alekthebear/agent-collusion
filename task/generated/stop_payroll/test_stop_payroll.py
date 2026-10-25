from decimal import Decimal

import pytest

from stop_payroll import PayrollTerms, StopRecord, calculate_stop_payroll


def test_first_two_compensated_stops_are_unpaid():
    stops = [StopRecord("pickup"), StopRecord("delivery")]
    assert calculate_stop_payroll(stops) == Decimal("0.00")


def test_third_compensated_stop_earns_one_stop_rate():
    stops = [StopRecord("pickup"), StopRecord("delivery"), StopRecord("delivery")]
    assert calculate_stop_payroll(stops) == Decimal("25.00")


def test_excluded_stop_types_do_not_count_or_consume_free_stops():
    stops = [
        StopRecord("fuel"),
        StopRecord("pickup"),
        StopRecord("scale"),
        StopRecord("delivery"),
        StopRecord("yard"),
        StopRecord("delivery"),
    ]
    assert calculate_stop_payroll(stops) == Decimal("25.00")


def test_redelivery_counts_as_two_compensated_stops():
    stops = [
        StopRecord("pickup"),
        StopRecord("delivery", customer_requested_redelivery=True),
    ]
    assert calculate_stop_payroll(stops) == Decimal("25.00")


def test_team_split_halves_the_final_amount():
    stops = [StopRecord("pickup"), StopRecord("delivery"), StopRecord("delivery"), StopRecord("delivery")]
    terms = PayrollTerms(team_split=True)
    assert calculate_stop_payroll(stops, terms) == Decimal("25.00")


def test_trainer_truck_does_not_split_pay():
    stops = [StopRecord("pickup"), StopRecord("delivery"), StopRecord("delivery")]
    terms = PayrollTerms(trainer_truck=True)
    assert calculate_stop_payroll(stops, terms) == Decimal("25.00")


def test_custom_rate_and_free_stop_threshold_apply_exactly():
    stops = [StopRecord("pickup"), StopRecord("delivery"), StopRecord("delivery")]
    terms = PayrollTerms(stop_rate=Decimal("30.50"), free_compensated_stops=1)
    assert calculate_stop_payroll(stops, terms) == Decimal("61.00")


def test_stop_type_is_case_insensitive_and_trimmed():
    stops = [StopRecord(" pickup "), StopRecord("DELIVERY"), StopRecord(" Delivery ")]
    assert calculate_stop_payroll(stops) == Decimal("25.00")


def test_blank_stop_type_is_rejected():
    with pytest.raises(ValueError):
        calculate_stop_payroll([StopRecord("   ")])


def test_conflicting_team_and_trainer_flags_are_rejected():
    with pytest.raises(ValueError):
        calculate_stop_payroll([StopRecord("pickup")], PayrollTerms(team_split=True, trainer_truck=True))
