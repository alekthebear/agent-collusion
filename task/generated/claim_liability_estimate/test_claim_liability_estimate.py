from decimal import Decimal

import pytest

from claim_liability_estimate import (
    ClaimFacts,
    LiabilityTerms,
    calculate_claim_liability_estimate,
)


def test_zero_proven_loss_returns_zero():
    facts = ClaimFacts(
        declared_value=Decimal("5000.00"),
        shipment_weight_lb=Decimal("1000"),
        damaged_weight_lb=Decimal("1000"),
        proven_loss_amount=Decimal("0.00"),
    )
    assert calculate_claim_liability_estimate(facts) == Decimal("0.00")


def test_base_loss_uses_lesser_of_declared_and_proven_loss():
    facts = ClaimFacts(
        declared_value=Decimal("4000.00"),
        shipment_weight_lb=Decimal("10000"),
        damaged_weight_lb=Decimal("9000"),
        proven_loss_amount=Decimal("4800.00"),
    )
    terms = LiabilityTerms(released_value_per_lb=None, deductible=Decimal("500.00"))
    assert calculate_claim_liability_estimate(facts, terms) == Decimal("3500.00")


def test_partial_loss_uses_damaged_weight_for_released_value_limit():
    facts = ClaimFacts(
        declared_value=Decimal("10000.00"),
        shipment_weight_lb=Decimal("1000"),
        damaged_weight_lb=Decimal("200"),
        proven_loss_amount=Decimal("5000.00"),
    )
    assert calculate_claim_liability_estimate(facts) == Decimal("100.00")


def test_total_loss_applies_contract_floor_when_weight_limit_is_lower():
    facts = ClaimFacts(
        declared_value=Decimal("10000.00"),
        shipment_weight_lb=Decimal("1000"),
        damaged_weight_lb=Decimal("1000"),
        proven_loss_amount=Decimal("9000.00"),
        is_total_loss=True,
    )
    assert calculate_claim_liability_estimate(facts) == Decimal("2000.00")


def test_salvage_reduces_liability_after_valuation():
    facts = ClaimFacts(
        declared_value=Decimal("8000.00"),
        shipment_weight_lb=Decimal("4000"),
        damaged_weight_lb=Decimal("4000"),
        proven_loss_amount=Decimal("3000.00"),
        salvage_recovery=Decimal("750.00"),
    )
    terms = LiabilityTerms(released_value_per_lb=None, deductible=Decimal("500.00"))
    assert calculate_claim_liability_estimate(facts, terms) == Decimal("1750.00")


def test_theft_total_loss_ignores_salvage_estimate():
    facts = ClaimFacts(
        declared_value=Decimal("6000.00"),
        shipment_weight_lb=Decimal("2000"),
        damaged_weight_lb=Decimal("2000"),
        proven_loss_amount=Decimal("6000.00"),
        salvage_recovery=Decimal("1000.00"),
        is_total_loss=True,
        is_theft=True,
    )
    terms = LiabilityTerms(released_value_per_lb=None, deductible=Decimal("500.00"))
    assert calculate_claim_liability_estimate(facts, terms) == Decimal("5500.00")


def test_small_claim_at_threshold_waives_deductible():
    facts = ClaimFacts(
        declared_value=Decimal("1200.00"),
        shipment_weight_lb=Decimal("1000"),
        damaged_weight_lb=Decimal("1000"),
        proven_loss_amount=Decimal("1000.00"),
    )
    terms = LiabilityTerms(released_value_per_lb=None, deductible=Decimal("500.00"))
    assert calculate_claim_liability_estimate(facts, terms) == Decimal("1000.00")


def test_hazmat_reserve_is_added_when_liability_remains():
    facts = ClaimFacts(
        declared_value=Decimal("2000.00"),
        shipment_weight_lb=Decimal("1000"),
        damaged_weight_lb=Decimal("1000"),
        proven_loss_amount=Decimal("1500.00"),
        is_hazmat_cleanup=True,
    )
    terms = LiabilityTerms(released_value_per_lb=None, deductible=Decimal("500.00"))
    assert calculate_claim_liability_estimate(facts, terms) == Decimal("1350.00")


def test_damaged_weight_cannot_exceed_shipment_weight():
    facts = ClaimFacts(
        declared_value=Decimal("1000.00"),
        shipment_weight_lb=Decimal("100"),
        damaged_weight_lb=Decimal("101"),
        proven_loss_amount=Decimal("500.00"),
    )
    with pytest.raises(ValueError):
        calculate_claim_liability_estimate(facts)
