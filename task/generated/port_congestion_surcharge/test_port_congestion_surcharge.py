from datetime import date, datetime
from decimal import Decimal

import pytest

from port_congestion_surcharge import (
    CongestionMove,
    calculate_port_congestion_surcharge,
)


def dt(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute)


def test_no_surcharge_before_program_effective_date():
    move = CongestionMove(
        service_date=date(2026, 3, 31),
        transaction_type="import",
        congestion_tier=3,
        gate_time=dt(2026, 3, 31, 10),
        hazardous=True,
    )
    assert calculate_port_congestion_surcharge(move) == Decimal("0.00")


def test_import_tier_one_uses_base_amount():
    move = CongestionMove(
        service_date=date(2026, 4, 1),
        transaction_type="import",
        congestion_tier=1,
        gate_time=dt(2026, 4, 1, 9),
    )
    assert calculate_port_congestion_surcharge(move) == Decimal("35.00")


def test_empty_transaction_uses_half_base_and_no_hazmat_addon():
    move = CongestionMove(
        service_date=date(2026, 4, 2),
        transaction_type="empty",
        congestion_tier=2,
        gate_time=dt(2026, 4, 2, 11),
        hazardous=True,
    )
    assert calculate_port_congestion_surcharge(move) == Decimal("30.00")


def test_street_turn_is_never_surcharged():
    move = CongestionMove(
        service_date=date(2026, 8, 8),
        transaction_type="street_turn",
        congestion_tier=3,
        gate_time=dt(2026, 8, 8, 12),
        hazardous=True,
        terminal_cap=Decimal("10.00"),
    )
    assert calculate_port_congestion_surcharge(move) == Decimal("0.00")


def test_weekend_premium_applies_only_at_tier_two_or_three():
    move = CongestionMove(
        service_date=date(2026, 4, 4),
        transaction_type="export",
        congestion_tier=2,
        gate_time=dt(2026, 4, 4, 8),
    )
    assert calculate_port_congestion_surcharge(move) == Decimal("80.00")


def test_late_arrival_more_than_thirty_minutes_cuts_total_in_half():
    move = CongestionMove(
        service_date=date(2026, 4, 6),
        transaction_type="import",
        congestion_tier=2,
        gate_time=dt(2026, 4, 6, 13, 0),
        appointment_time=dt(2026, 4, 6, 8, 0),
        arrival_time=dt(2026, 4, 6, 8, 31),
    )
    assert calculate_port_congestion_surcharge(move) == Decimal("30.00")


def test_exactly_thirty_minutes_late_does_not_reduce_charge():
    move = CongestionMove(
        service_date=date(2026, 4, 6),
        transaction_type="import",
        congestion_tier=2,
        gate_time=dt(2026, 4, 6, 12, 0),
        appointment_time=dt(2026, 4, 6, 8, 0),
        arrival_time=dt(2026, 4, 6, 8, 30),
    )
    assert calculate_port_congestion_surcharge(move) == Decimal("60.00")


def test_severe_delay_premium_starts_on_effective_date():
    move = CongestionMove(
        service_date=date(2026, 7, 1),
        transaction_type="export",
        congestion_tier=3,
        gate_time=dt(2026, 7, 1, 11, 1),
        appointment_time=dt(2026, 7, 1, 8, 0),
        arrival_time=dt(2026, 7, 1, 7, 50),
    )
    assert calculate_port_congestion_surcharge(move) == Decimal("120.00")


def test_terminal_cap_limits_total_after_addons():
    move = CongestionMove(
        service_date=date(2026, 7, 5),
        transaction_type="import",
        congestion_tier=3,
        gate_time=dt(2026, 7, 5, 14, 0),
        appointment_time=dt(2026, 7, 5, 9, 0),
        arrival_time=dt(2026, 7, 5, 9, 0),
        hazardous=True,
        terminal_cap=Decimal("100.00"),
    )
    assert calculate_port_congestion_surcharge(move) == Decimal("100.00")


def test_arrival_without_appointment_is_rejected():
    move = CongestionMove(
        service_date=date(2026, 4, 3),
        transaction_type="import",
        congestion_tier=1,
        gate_time=dt(2026, 4, 3, 10),
        arrival_time=dt(2026, 4, 3, 9, 45),
    )
    with pytest.raises(ValueError):
        calculate_port_congestion_surcharge(move)
