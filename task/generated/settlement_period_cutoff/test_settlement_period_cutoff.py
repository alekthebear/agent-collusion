from datetime import datetime, date
from decimal import Decimal

import pytest

from settlement_period_cutoff import SettlementInputs, calculate_settlement_period_cutoff


def dt(y, m, d, hh=0, mm=0):
    return datetime(y, m, d, hh, mm)


def test_standard_load_uses_later_of_delivery_and_paperwork():
    load = SettlementInputs(
        delivery_at=dt(2026, 4, 7, 10),
        paperwork_received_at=dt(2026, 4, 8, 11),
    )
    assert calculate_settlement_period_cutoff(load) == date(2026, 4, 10)


def test_paperwork_after_cutoff_counts_next_business_day():
    load = SettlementInputs(
        delivery_at=dt(2026, 4, 7, 9),
        paperwork_received_at=dt(2026, 4, 10, 15, 1),
    )
    assert calculate_settlement_period_cutoff(load) == date(2026, 4, 17)


def test_weekend_paperwork_rolls_to_monday():
    load = SettlementInputs(
        delivery_at=dt(2026, 4, 9, 14),
        paperwork_received_at=dt(2026, 4, 11, 10),
    )
    assert calculate_settlement_period_cutoff(load) == date(2026, 4, 17)


def test_missing_paperwork_requires_approval():
    load = SettlementInputs(delivery_at=dt(2026, 4, 8, 10))
    with pytest.raises(ValueError):
        calculate_settlement_period_cutoff(load)


def test_missing_paperwork_uses_approval_but_not_before_delivery():
    load = SettlementInputs(
        delivery_at=dt(2026, 4, 8, 16),
        approved_at=dt(2026, 4, 6, 9),
    )
    assert calculate_settlement_period_cutoff(load) == date(2026, 4, 10)


def test_hazmat_adds_one_business_day():
    load = SettlementInputs(
        delivery_at=dt(2026, 4, 9, 8),
        paperwork_received_at=dt(2026, 4, 9, 9),
        hazmat=True,
    )
    assert calculate_settlement_period_cutoff(load) == date(2026, 4, 17)


def test_high_value_without_manager_approval_adds_two_business_days():
    load = SettlementInputs(
        delivery_at=dt(2026, 4, 8, 8),
        paperwork_received_at=dt(2026, 4, 8, 9),
        invoice_amount=Decimal("100000.00"),
    )
    assert calculate_settlement_period_cutoff(load) == date(2026, 4, 17)


def test_high_value_with_manager_approval_adds_one_business_day():
    load = SettlementInputs(
        delivery_at=dt(2026, 4, 9, 8),
        paperwork_received_at=dt(2026, 4, 9, 9),
        invoice_amount=Decimal("250000.00"),
        manager_approved=True,
    )
    assert calculate_settlement_period_cutoff(load) == date(2026, 4, 17)


def test_frozen_friday_after_1700_moves_to_following_friday():
    load = SettlementInputs(
        delivery_at=dt(2026, 4, 10, 17, 1),
        paperwork_received_at=dt(2026, 4, 10, 14, 0),
        frozen=True,
    )
    assert calculate_settlement_period_cutoff(load) == date(2026, 4, 17)


def test_negative_invoice_amount_is_rejected():
    load = SettlementInputs(
        delivery_at=dt(2026, 4, 8, 10),
        paperwork_received_at=dt(2026, 4, 8, 12),
        invoice_amount=Decimal("-1.00"),
    )
    with pytest.raises(ValueError):
        calculate_settlement_period_cutoff(load)
