from datetime import datetime
from decimal import Decimal

import pytest

from layover_payroll import LayoverEvent, LayoverTerms, calculate_layover_payroll


def at(day, hour=0, minute=0):
    return datetime(2026, 3, day, hour, minute)


def test_under_24_hours_does_not_qualify():
    event = LayoverEvent(released_at=at(1, 8), dispatched_at=at(2, 7, 59))
    assert calculate_layover_payroll(event) == Decimal("0.00")


def test_exactly_24_hours_pays_one_flat_day():
    event = LayoverEvent(released_at=at(1, 8), dispatched_at=at(2, 8))
    assert calculate_layover_payroll(event) == Decimal("125.00")


def test_exactly_48_hours_pays_two_flat_days():
    event = LayoverEvent(released_at=at(1, 8), dispatched_at=at(3, 8))
    assert calculate_layover_payroll(event) == Decimal("250.00")


def test_partial_extra_day_is_not_paid():
    event = LayoverEvent(released_at=at(1, 8), dispatched_at=at(4, 7, 59))
    assert calculate_layover_payroll(event) == Decimal("250.00")


def test_tiered_schedule_applies_from_configured_day():
    event = LayoverEvent(released_at=at(1, 8), dispatched_at=at(5, 8))
    terms = LayoverTerms(tier2_start_day=2, tier2_day_rate=Decimal("150.00"))
    assert calculate_layover_payroll(event, terms) == Decimal("575.00")


def test_team_operation_never_gets_layover():
    event = LayoverEvent(released_at=at(1, 8), dispatched_at=at(5, 8), is_team_operation=True)
    assert calculate_layover_payroll(event) == Decimal("0.00")


def test_union_hotel_program_suppresses_pay():
    event = LayoverEvent(released_at=at(1, 8), dispatched_at=at(4, 8), hotel_program_paid=True)
    terms = LayoverTerms(union_driver=True)
    assert calculate_layover_payroll(event, terms) == Decimal("0.00")


def test_breakdown_rate_uses_lower_special_rate_and_caps_days():
    event = LayoverEvent(released_at=at(1, 8), dispatched_at=at(6, 8), breakdown_related=True)
    terms = LayoverTerms(breakdown_day_rate=Decimal("100.00"), breakdown_max_days=2)
    assert calculate_layover_payroll(event, terms) == Decimal("200.00")


def test_dispatch_before_release_is_rejected():
    event = LayoverEvent(released_at=at(2, 8), dispatched_at=at(1, 8))
    with pytest.raises(ValueError):
        calculate_layover_payroll(event)
