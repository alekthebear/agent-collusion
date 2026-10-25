from datetime import date

import pytest

from claim_filing_deadline import ClaimTerms, DeliveryFacts, calculate_claim_filing_deadline


def test_visible_damage_uses_default_base_period_and_moves_sunday_to_monday():
    facts = DeliveryFacts(delivered_on=date(2026, 1, 1))
    assert calculate_claim_filing_deadline(facts) == date(2026, 9, 28)


def test_concealed_damage_uses_earlier_notice_window_and_moves_saturday_to_friday():
    facts = DeliveryFacts(delivered_on=date(2026, 3, 2), concealed_damage=True)
    assert calculate_claim_filing_deadline(facts) == date(2026, 3, 6)


def test_same_day_exception_preserves_base_period_for_concealed_damage():
    facts = DeliveryFacts(
        delivered_on=date(2026, 3, 2), concealed_damage=True, noted_at_delivery=True
    )
    assert calculate_claim_filing_deadline(facts) == date(2026, 11, 27)


def test_contract_day_limit_controls_when_earlier_than_year_limit():
    facts = DeliveryFacts(delivered_on=date(2026, 4, 1))
    terms = ClaimTerms(contract_limit_days=300, contract_limit_years=3)
    assert calculate_claim_filing_deadline(facts, terms) == date(2027, 1, 26)


def test_earlier_of_day_and_year_limits_controls():
    facts = DeliveryFacts(delivered_on=date(2026, 6, 15))
    terms = ClaimTerms(contract_limit_days=800, contract_limit_years=2)
    assert calculate_claim_filing_deadline(facts, terms) == date(2028, 6, 15)


def test_sunday_deadline_moves_to_monday():
    facts = DeliveryFacts(delivered_on=date(2026, 3, 6), concealed_damage=True)
    assert calculate_claim_filing_deadline(facts) == date(2026, 3, 11)


def test_leap_day_anniversary_falls_back_to_february_28():
    facts = DeliveryFacts(delivered_on=date(2024, 2, 29))
    terms = ClaimTerms(contract_limit_days=1000, contract_limit_years=1, statutory_limit_years=1)
    assert calculate_claim_filing_deadline(facts, terms) == date(2025, 2, 28)


def test_contract_cannot_shorten_below_statutory_floor():
    facts = DeliveryFacts(delivered_on=date(2026, 5, 1))
    with pytest.raises(ValueError):
        calculate_claim_filing_deadline(facts, ClaimTerms(contract_limit_days=269))


def test_noted_at_delivery_without_concealed_damage_is_rejected():
    facts = DeliveryFacts(delivered_on=date(2026, 5, 1), noted_at_delivery=True)
    with pytest.raises(ValueError):
        calculate_claim_filing_deadline(facts)
