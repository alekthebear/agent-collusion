from datetime import date
from decimal import Decimal

import pytest

from escrow_withholding import (
    DEFAULT_HOLD_DAYS,
    EscrowAccount,
    WeeklySettlement,
    calculate_escrow_withholding,
)


def test_small_settlement_is_protected_from_withholding():
    account = EscrowAccount(current_balance=Decimal("100.00"), cap=Decimal("1000.00"))
    settlement = WeeklySettlement(week_end=date(2026, 4, 10), gross_pay=Decimal("249.99"))
    result = calculate_escrow_withholding(account, settlement)
    assert result.withheld == Decimal("0.00")
    assert result.released == Decimal("0.00")
    assert result.ending_balance == Decimal("100.00")


def test_settlement_at_protected_threshold_still_withholds():
    account = EscrowAccount(current_balance=Decimal("100.00"), cap=Decimal("1000.00"))
    settlement = WeeklySettlement(week_end=date(2026, 4, 10), gross_pay=Decimal("250.00"))
    result = calculate_escrow_withholding(account, settlement)
    assert result.withheld == Decimal("25.00")
    assert result.ending_balance == Decimal("125.00")


def test_large_settlement_is_capped_at_max_weekly_withhold():
    account = EscrowAccount(current_balance=Decimal("300.00"), cap=Decimal("2000.00"))
    settlement = WeeklySettlement(week_end=date(2026, 4, 10), gross_pay=Decimal("3000.00"))
    result = calculate_escrow_withholding(account, settlement)
    assert result.withheld == Decimal("250.00")
    assert result.released == Decimal("0.00")
    assert result.ending_balance == Decimal("550.00")


def test_withholding_does_not_exceed_remaining_to_cap():
    account = EscrowAccount(current_balance=Decimal("990.00"), cap=Decimal("1000.00"))
    settlement = WeeklySettlement(week_end=date(2026, 4, 10), gross_pay=Decimal("800.00"))
    result = calculate_escrow_withholding(account, settlement)
    assert result.withheld == Decimal("10.00")
    assert result.ending_balance == Decimal("1000.00")


def test_balance_already_at_cap_has_no_withholding():
    account = EscrowAccount(current_balance=Decimal("1000.00"), cap=Decimal("1000.00"))
    settlement = WeeklySettlement(week_end=date(2026, 4, 10), gross_pay=Decimal("1500.00"))
    result = calculate_escrow_withholding(account, settlement)
    assert result.withheld == Decimal("0.00")
    assert result.ending_balance == Decimal("1000.00")


def test_release_request_blocks_new_withholding():
    account = EscrowAccount(current_balance=Decimal("400.00"), cap=Decimal("1000.00"), release_requested=True)
    settlement = WeeklySettlement(week_end=date(2026, 4, 10), gross_pay=Decimal("1200.00"))
    result = calculate_escrow_withholding(account, settlement)
    assert result.withheld == Decimal("0.00")
    assert result.released == Decimal("0.00")
    assert result.ending_balance == Decimal("400.00")


def test_terminated_account_releases_after_hold_period():
    account = EscrowAccount(
        current_balance=Decimal("650.00"),
        cap=Decimal("1000.00"),
        terminated=True,
        termination_date=date(2026, 3, 1),
    )
    settlement = WeeklySettlement(
        week_end=date(2026, 3, 1).fromordinal(date(2026, 3, 1).toordinal() + DEFAULT_HOLD_DAYS),
        gross_pay=Decimal("0.00"),
    )
    result = calculate_escrow_withholding(account, settlement)
    assert result.withheld == Decimal("0.00")
    assert result.released == Decimal("650.00")
    assert result.ending_balance == Decimal("0.00")


def test_terminated_account_before_release_date_does_not_release():
    account = EscrowAccount(
        current_balance=Decimal("650.00"),
        cap=Decimal("1000.00"),
        terminated=True,
        termination_date=date(2026, 3, 1),
    )
    settlement = WeeklySettlement(week_end=date(2026, 3, 20), gross_pay=Decimal("0.00"))
    result = calculate_escrow_withholding(account, settlement)
    assert result.released == Decimal("0.00")
    assert result.ending_balance == Decimal("650.00")


def test_terminated_account_requires_termination_date():
    account = EscrowAccount(current_balance=Decimal("100.00"), cap=Decimal("500.00"), terminated=True)
    settlement = WeeklySettlement(week_end=date(2026, 4, 10), gross_pay=Decimal("1000.00"))
    with pytest.raises(ValueError):
        calculate_escrow_withholding(account, settlement)
