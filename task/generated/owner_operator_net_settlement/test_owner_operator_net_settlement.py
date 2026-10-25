from decimal import Decimal

import pytest

from owner_operator_net_settlement import (
    MIN_COMMISSION,
    SettlementInputs,
    calculate_owner_operator_net_settlement,
)


def test_reimbursements_increase_net_but_not_commissionable():
    s = SettlementInputs(
        linehaul=Decimal("1000.00"),
        reimbursements=Decimal("200.00"),
        occupational_accident_exempt=True,
        reserve_target=Decimal("0.00"),
    )
    result = calculate_owner_operator_net_settlement(s)
    assert result.commission_withheld == Decimal("250.00")
    assert result.net_settlement == Decimal("950.00")


def test_small_load_uses_minimum_commission_floor():
    s = SettlementInputs(
        linehaul=Decimal("100.00"),
        occupational_accident_exempt=True,
        reserve_target=Decimal("0.00"),
    )
    result = calculate_owner_operator_net_settlement(s)
    assert result.commission_withheld == MIN_COMMISSION
    assert result.net_settlement == Decimal("65.00")


def test_reserve_stops_at_remaining_gap_to_target():
    s = SettlementInputs(
        linehaul=Decimal("1000.00"),
        reserve_balance=Decimal("950.00"),
        reserve_target=Decimal("1000.00"),
        reserve_contribution=Decimal("100.00"),
        occupational_accident_exempt=True,
    )
    result = calculate_owner_operator_net_settlement(s)
    assert result.reserve_withheld == Decimal("50.00")
    assert result.net_settlement == Decimal("700.00")


def test_no_reserve_taken_on_zero_or_negative_prereserve_week():
    s = SettlementInputs(
        linehaul=Decimal("50.00"),
        commission_rate=Decimal("0.50"),
        reserve_contribution=Decimal("100.00"),
        occupational_accident_exempt=False,
    )
    result = calculate_owner_operator_net_settlement(s)
    assert result.commission_withheld == Decimal("35.00")
    assert result.reserve_withheld == Decimal("0.00")
    assert result.net_settlement == Decimal("0.00")


def test_occupational_accident_waived_when_exempt():
    s = SettlementInputs(
        linehaul=Decimal("400.00"),
        occupational_accident_exempt=True,
        reserve_target=Decimal("0.00"),
    )
    result = calculate_owner_operator_net_settlement(s)
    assert result.occupational_accident_withheld == Decimal("0.00")
    assert result.net_settlement == Decimal("300.00")


def test_minimum_net_pay_reduces_reserve_first():
    s = SettlementInputs(
        linehaul=Decimal("600.00"),
        reserve_contribution=Decimal("100.00"),
        occupational_accident_exempt=True,
        minimum_net_pay=Decimal("380.00"),
    )
    result = calculate_owner_operator_net_settlement(s)
    assert result.commission_withheld == Decimal("150.00")
    assert result.reserve_withheld == Decimal("70.00")
    assert result.net_settlement == Decimal("380.00")


def test_minimum_net_pay_can_reduce_commission_but_not_below_floor():
    s = SettlementInputs(
        linehaul=Decimal("300.00"),
        reserve_contribution=Decimal("100.00"),
        occupational_accident_exempt=True,
        minimum_net_pay=Decimal("240.00"),
    )
    result = calculate_owner_operator_net_settlement(s)
    assert result.reserve_withheld == Decimal("0.00")
    assert result.commission_withheld == Decimal("60.00")
    assert result.net_settlement == Decimal("240.00")


def test_negative_result_is_clamped_to_zero_after_all_deductions():
    s = SettlementInputs(
        linehaul=Decimal("200.00"),
        trailer_rent=Decimal("300.00"),
        occupational_accident_exempt=True,
        reserve_target=Decimal("0.00"),
    )
    result = calculate_owner_operator_net_settlement(s)
    assert result.net_settlement == Decimal("0.00")


def test_invalid_negative_money_is_rejected():
    with pytest.raises(ValueError):
        calculate_owner_operator_net_settlement(
            SettlementInputs(linehaul=Decimal("-1.00"))
        )
