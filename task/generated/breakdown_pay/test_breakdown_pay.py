from datetime import datetime
from decimal import Decimal

import pytest

from breakdown_pay import BreakdownEvent, BreakdownTerms, calculate_breakdown_pay


def at(day, hour, minute=0):
    return datetime(2026, 4, day, hour, minute)


def test_within_free_time_is_unpaid():
    event = BreakdownEvent(reported_at=at(2, 8), repaired_at=at(2, 10))
    assert calculate_breakdown_pay(event) == Decimal("0.00")


def test_started_half_hour_is_billed_in_full():
    event = BreakdownEvent(reported_at=at(2, 8), repaired_at=at(2, 10, 1))
    assert calculate_breakdown_pay(event) == Decimal("9.00")


def test_shop_time_starts_at_check_in_when_later_than_report():
    event = BreakdownEvent(reported_at=at(2, 8), shop_in_at=at(2, 9), repaired_at=at(2, 12))
    assert calculate_breakdown_pay(event) == Decimal("18.00")


def test_roadside_ignores_shop_in_and_adds_premium():
    event = BreakdownEvent(
        reported_at=at(2, 8),
        shop_in_at=at(2, 9),
        repaired_at=at(2, 12),
        roadside=True,
    )
    assert calculate_breakdown_pay(event) == Decimal("71.00")


def test_overnight_stipend_applies_per_midnight_crossed():
    event = BreakdownEvent(reported_at=at(2, 22), repaired_at=at(3, 3))
    assert calculate_breakdown_pay(event) == Decimal("139.00")


def test_declined_hotel_blocks_overnight_stipend():
    event = BreakdownEvent(
        reported_at=at(2, 22),
        repaired_at=at(3, 3),
        hotel_offered=True,
        hotel_declined=True,
    )
    assert calculate_breakdown_pay(event) == Decimal("54.00")


def test_daily_cap_uses_calendar_days_touched_by_compensated_period():
    event = BreakdownEvent(reported_at=at(2, 8), repaired_at=at(4, 20))
    assert calculate_breakdown_pay(event) == Decimal("500.00")
    terms = BreakdownTerms(claim_cap=None)
    assert calculate_breakdown_pay(event, terms) == Decimal("600.00")


def test_claim_cap_applies_after_other_amounts():
    event = BreakdownEvent(
        reported_at=at(2, 8),
        repaired_at=at(4, 20),
        roadside=True,
    )
    assert calculate_breakdown_pay(event) == Decimal("500.00")


def test_invalid_time_order_is_rejected():
    with pytest.raises(ValueError):
        calculate_breakdown_pay(BreakdownEvent(reported_at=at(2, 10), repaired_at=at(2, 9)))


def test_decline_without_offer_is_rejected():
    with pytest.raises(ValueError):
        calculate_breakdown_pay(
            BreakdownEvent(reported_at=at(2, 8), repaired_at=at(2, 12), hotel_declined=True)
        )
