from decimal import Decimal

import pytest

from owner_operator_linehaul_settlement import (
    PayBasis,
    SettlementDeductions,
    SettlementTerms,
    calculate_owner_operator_linehaul_settlement,
)


def test_percentage_pay_basis_rounds_half_up_to_cent():
    result = calculate_owner_operator_linehaul_settlement(
        gross_linehaul=Decimal("1234.56"),
        loaded_miles=500,
        pay_basis=PayBasis(percent_of_linehaul=Decimal("0.725")),
    )
    assert result == Decimal("895.06")


def test_mileage_pay_basis_uses_loaded_miles_and_rate():
    result = calculate_owner_operator_linehaul_settlement(
        gross_linehaul=Decimal("9999.99"),
        loaded_miles=423,
        pay_basis=PayBasis(rate_per_loaded_mile=Decimal("1.38")),
    )
    assert result == Decimal("583.74")


def test_guaranteed_minimum_raises_gross_before_deductions():
    result = calculate_owner_operator_linehaul_settlement(
        gross_linehaul=Decimal("500.00"),
        loaded_miles=100,
        pay_basis=PayBasis(percent_of_linehaul=Decimal("0.70")),
        terms=SettlementTerms(guaranteed_minimum_gross=Decimal("400.00")),
    )
    assert result == Decimal("400.00")


def test_cap_applies_after_minimum():
    result = calculate_owner_operator_linehaul_settlement(
        gross_linehaul=Decimal("500.00"),
        loaded_miles=100,
        pay_basis=PayBasis(percent_of_linehaul=Decimal("0.70")),
        terms=SettlementTerms(
            guaranteed_minimum_gross=Decimal("400.00"),
            gross_pay_cap=Decimal("375.00"),
        ),
    )
    assert result == Decimal("375.00")


def test_escrow_only_collects_up_to_target_balance():
    result = calculate_owner_operator_linehaul_settlement(
        gross_linehaul=Decimal("1000.00"),
        loaded_miles=0,
        pay_basis=PayBasis(percent_of_linehaul=Decimal("0.80")),
        deductions=SettlementDeductions(
            escrow_request=Decimal("100.00"),
            escrow_balance=Decimal("450.00"),
            escrow_target=Decimal("500.00"),
        ),
    )
    assert result == Decimal("750.00")


def test_unauthorized_deductions_and_unenrolled_occ_acc_are_ignored():
    result = calculate_owner_operator_linehaul_settlement(
        gross_linehaul=Decimal("1000.00"),
        loaded_miles=0,
        pay_basis=PayBasis(percent_of_linehaul=Decimal("0.80")),
        deductions=SettlementDeductions(
            occupational_accident=Decimal("35.00"),
            occ_acc_enrolled=False,
            device_rental=Decimal("20.00"),
            device_rental_authorized=False,
            chargeback=Decimal("60.00"),
            chargeback_authorized=False,
        ),
    )
    assert result == Decimal("800.00")


def test_authorized_deductions_reduce_net():
    result = calculate_owner_operator_linehaul_settlement(
        gross_linehaul=Decimal("1000.00"),
        loaded_miles=0,
        pay_basis=PayBasis(percent_of_linehaul=Decimal("0.80")),
        deductions=SettlementDeductions(
            occupational_accident=Decimal("35.00"),
            occ_acc_enrolled=True,
            device_rental=Decimal("20.00"),
            device_rental_authorized=True,
            chargeback=Decimal("60.00"),
            chargeback_authorized=True,
        ),
    )
    assert result == Decimal("685.00")


def test_net_floor_limits_deductions_from_driving_net_lower():
    result = calculate_owner_operator_linehaul_settlement(
        gross_linehaul=Decimal("600.00"),
        loaded_miles=0,
        pay_basis=PayBasis(percent_of_linehaul=Decimal("0.75")),
        deductions=SettlementDeductions(
            chargeback=Decimal("200.00"),
            chargeback_authorized=True,
        ),
        terms=SettlementTerms(net_floor=Decimal("300.00")),
    )
    assert result == Decimal("300.00")


def test_invalid_pay_basis_configuration_is_rejected():
    with pytest.raises(ValueError):
        calculate_owner_operator_linehaul_settlement(
            gross_linehaul=Decimal("1000.00"),
            loaded_miles=100,
            pay_basis=PayBasis(
                percent_of_linehaul=Decimal("0.80"),
                rate_per_loaded_mile=Decimal("1.50"),
            ),
        )


def test_negative_gross_linehaul_is_rejected():
    with pytest.raises(ValueError):
        calculate_owner_operator_linehaul_settlement(
            gross_linehaul=Decimal("-1.00"),
            loaded_miles=100,
            pay_basis=PayBasis(percent_of_linehaul=Decimal("0.80")),
        )
