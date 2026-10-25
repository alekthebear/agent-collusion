from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from spotting_fee import SpottingTerms, SpottingWork, calculate_spotting_fee


def test_no_work_is_zero_charge():
    work = SpottingWork(moved_at=datetime(2026, 4, 1, 9, 0), move_count=0)
    assert calculate_spotting_fee(work) == Decimal("0.00")


def test_minimum_applies_to_single_shared_move():
    work = SpottingWork(moved_at=datetime(2026, 4, 1, 9, 0), move_count=1)
    assert calculate_spotting_fee(work) == Decimal("65.00")


def test_multiple_moves_bill_above_minimum():
    work = SpottingWork(moved_at=datetime(2026, 4, 1, 9, 0), move_count=3)
    assert calculate_spotting_fee(work) == Decimal("97.50")


def test_standby_within_included_time_is_not_billed():
    work = SpottingWork(
        moved_at=datetime(2026, 4, 1, 9, 0),
        move_count=2,
        standby=timedelta(minutes=30),
    )
    assert calculate_spotting_fee(work) == Decimal("65.00")


def test_partial_standby_increment_rounds_up():
    work = SpottingWork(
        moved_at=datetime(2026, 4, 1, 9, 0),
        move_count=2,
        standby=timedelta(minutes=31),
    )
    assert calculate_spotting_fee(work) == Decimal("82.00")


def test_dedicated_single_move_with_standby_waives_positioning_move():
    work = SpottingWork(
        moved_at=datetime(2026, 4, 1, 9, 0),
        move_count=1,
        standby=timedelta(minutes=50),
    )
    terms = SpottingTerms(hostler_type="dedicated")
    assert calculate_spotting_fee(work, terms) == Decimal("65.00")


def test_dedicated_gets_minimum_45_included_standby_minutes():
    work = SpottingWork(
        moved_at=datetime(2026, 4, 1, 9, 0),
        move_count=2,
        standby=timedelta(minutes=50),
    )
    terms = SpottingTerms(hostler_type="dedicated")
    assert calculate_spotting_fee(work, terms) == Decimal("82.00")


def test_overnight_single_shared_move_is_waived_when_no_billable_standby():
    work = SpottingWork(
        moved_at=datetime(2026, 4, 1, 2, 0),
        move_count=1,
        overnight_quiet_hours=True,
    )
    assert calculate_spotting_fee(work) == Decimal("0.00")


def test_contractor_caps_included_standby_at_fifteen_minutes():
    work = SpottingWork(
        moved_at=datetime(2026, 4, 1, 9, 0),
        move_count=2,
        standby=timedelta(minutes=20),
    )
    terms = SpottingTerms(hostler_type="contractor")
    assert calculate_spotting_fee(work, terms) == Decimal("82.00")


def test_negative_move_count_is_rejected():
    work = SpottingWork(moved_at=datetime(2026, 4, 1, 9, 0), move_count=-1)
    with pytest.raises(ValueError):
        calculate_spotting_fee(work)
