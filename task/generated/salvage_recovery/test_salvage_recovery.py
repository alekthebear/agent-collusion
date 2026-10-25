from decimal import Decimal

import pytest

from salvage_recovery import SalvageInputs, calculate_salvage_recovery


def test_uses_larger_of_estimated_salvage_and_known_recovery_value():
    claim = SalvageInputs(
        gross_claim=Decimal("1000.00"),
        salvage_percent=Decimal("10"),
        recovery_value=Decimal("180.00"),
        disposal_cost=Decimal("20.00"),
    )
    result = calculate_salvage_recovery(claim)
    assert result.estimated_salvage == Decimal("100.00")
    assert result.gross_salvage_credit == Decimal("180.00")
    assert result.net_salvage_credit == Decimal("160.00")
    assert result.net_exposure == Decimal("840.00")


def test_disposal_cost_can_zero_out_salvage_credit():
    claim = SalvageInputs(
        gross_claim=Decimal("500.00"),
        salvage_percent=Decimal("8"),
        recovery_value=Decimal("0.00"),
        disposal_cost=Decimal("60.00"),
    )
    result = calculate_salvage_recovery(claim)
    assert result.net_salvage_credit == Decimal("0.00")
    assert result.net_exposure == Decimal("500.00")


def test_hazmat_only_collects_eighty_percent_of_net_salvage():
    claim = SalvageInputs(
        gross_claim=Decimal("1000.00"),
        salvage_percent=Decimal("20"),
        disposal_cost=Decimal("50.00"),
        hazmat=True,
    )
    result = calculate_salvage_recovery(claim)
    assert result.net_salvage_credit == Decimal("120.00")
    assert result.net_exposure == Decimal("880.00")


def test_immaterial_salvage_under_twenty_five_is_ignored():
    claim = SalvageInputs(
        gross_claim=Decimal("200.00"),
        salvage_percent=Decimal("12"),
    )
    result = calculate_salvage_recovery(claim)
    assert result.net_salvage_credit == Decimal("0.00")
    assert result.net_exposure == Decimal("200.00")


def test_salvage_equal_to_immaterial_threshold_is_credited():
    claim = SalvageInputs(
        gross_claim=Decimal("250.00"),
        salvage_percent=Decimal("10"),
    )
    result = calculate_salvage_recovery(claim)
    assert result.net_salvage_credit == Decimal("25.00")
    assert result.net_exposure == Decimal("225.00")


def test_insurer_takes_share_only_above_deductible():
    claim = SalvageInputs(
        gross_claim=Decimal("2000.00"),
        salvage_percent=Decimal("40"),
        deductible=Decimal("500.00"),
        insurer_participates=True,
    )
    result = calculate_salvage_recovery(claim)
    assert result.net_salvage_credit == Decimal("800.00")
    assert result.insurer_salvage_credit == Decimal("210.00")
    assert result.tidewater_salvage_credit == Decimal("590.00")
    assert result.net_exposure == Decimal("1200.00")


def test_without_insurer_participation_tidewater_gets_all_salvage_credit():
    claim = SalvageInputs(
        gross_claim=Decimal("2000.00"),
        salvage_percent=Decimal("40"),
        insurer_participates=False,
    )
    result = calculate_salvage_recovery(claim)
    assert result.tidewater_salvage_credit == Decimal("800.00")
    assert result.insurer_salvage_credit == Decimal("0.00")


def test_claim_at_or_below_deductible_has_no_insurer_salvage_share():
    claim = SalvageInputs(
        gross_claim=Decimal("400.00"),
        salvage_percent=Decimal("25"),
        deductible=Decimal("500.00"),
    )
    result = calculate_salvage_recovery(claim)
    assert result.net_salvage_credit == Decimal("100.00")
    assert result.tidewater_salvage_credit == Decimal("100.00")
    assert result.insurer_salvage_credit == Decimal("0.00")


def test_salvage_credit_cannot_exceed_gross_claim():
    claim = SalvageInputs(
        gross_claim=Decimal("300.00"),
        salvage_percent=Decimal("50"),
        recovery_value=Decimal("500.00"),
    )
    result = calculate_salvage_recovery(claim)
    assert result.gross_salvage_credit == Decimal("500.00")
    assert result.net_salvage_credit == Decimal("300.00")
    assert result.net_exposure == Decimal("0.00")


def test_invalid_salvage_percent_is_rejected():
    with pytest.raises(ValueError):
        calculate_salvage_recovery(
            SalvageInputs(gross_claim=Decimal("100.00"), salvage_percent=Decimal("101"))
        )
