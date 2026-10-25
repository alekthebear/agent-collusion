from decimal import Decimal

import pytest

from claim_pro_rata_allocation import Allocation, ClaimShare, allocate_claim_pro_rata


def test_allocates_by_basis_in_input_order():
    shares = [
        ClaimShare("line-1", Decimal("100")),
        ClaimShare("line-2", Decimal("300")),
    ]
    assert allocate_claim_pro_rata(Decimal("80.00"), shares) == [
        Allocation("line-1", Decimal("20.00")),
        Allocation("line-2", Decimal("60.00")),
    ]


def test_zero_claim_returns_zero_for_all_including_excluded():
    shares = [
        ClaimShare("pkg-a", Decimal("10"), excluded=True),
        ClaimShare("pkg-b", Decimal("20")),
    ]
    assert allocate_claim_pro_rata(Decimal("0.00"), shares) == [
        Allocation("pkg-a", Decimal("0.00")),
        Allocation("pkg-b", Decimal("0.00")),
    ]


def test_excluded_party_gets_nothing_and_basis_is_ignored():
    shares = [
        ClaimShare("carrier-a", Decimal("50"), excluded=True),
        ClaimShare("carrier-b", Decimal("50")),
    ]
    assert allocate_claim_pro_rata(Decimal("40.00"), shares) == [
        Allocation("carrier-a", Decimal("0.00")),
        Allocation("carrier-b", Decimal("40.00")),
    ]


def test_zero_total_basis_assigns_entire_claim_to_first_eligible():
    shares = [
        ClaimShare("first", Decimal("0")),
        ClaimShare("second", Decimal("0")),
    ]
    assert allocate_claim_pro_rata(Decimal("33.33"), shares) == [
        Allocation("first", Decimal("33.33")),
        Allocation("second", Decimal("0.00")),
    ]


def test_minimum_amount_acts_as_floor():
    shares = [
        ClaimShare("a", Decimal("90"), minimum_amount=Decimal("10.00")),
        ClaimShare("b", Decimal("10"), minimum_amount=Decimal("0.00")),
    ]
    assert allocate_claim_pro_rata(Decimal("10.50"), shares) == [
        Allocation("a", Decimal("10.00")),
        Allocation("b", Decimal("0.50")),
    ]


def test_fault_percent_sets_higher_floor_than_basis_share():
    shares = [
        ClaimShare("at-fault", Decimal("10"), fault_percent=Decimal("50")),
        ClaimShare("other", Decimal("90")),
    ]
    assert allocate_claim_pro_rata(Decimal("20.00"), shares) == [
        Allocation("at-fault", Decimal("10.00")),
        Allocation("other", Decimal("10.00")),
    ]


def test_largest_remainder_gets_extra_cent_after_round_down():
    shares = [
        ClaimShare("a", Decimal("1")),
        ClaimShare("b", Decimal("1")),
        ClaimShare("c", Decimal("1")),
    ]
    assert allocate_claim_pro_rata(Decimal("0.05"), shares) == [
        Allocation("a", Decimal("0.01")),
        Allocation("b", Decimal("0.02")),
        Allocation("c", Decimal("0.02")),
    ]


def test_cap_limits_party_and_remainder_moves_to_uncapped_party():
    shares = [
        ClaimShare("capped", Decimal("1"), declared_value_cap=Decimal("10.00")),
        ClaimShare("uncapped", Decimal("1")),
    ]
    assert allocate_claim_pro_rata(Decimal("30.00"), shares) == [
        Allocation("capped", Decimal("10.00")),
        Allocation("uncapped", Decimal("20.00")),
    ]


def test_invalid_negative_values_are_rejected():
    with pytest.raises(ValueError):
        allocate_claim_pro_rata(Decimal("10.00"), [ClaimShare("bad", Decimal("-1"))])


def test_floor_cannot_exceed_declared_value_cap():
    shares = [
        ClaimShare("pkg", Decimal("100"), minimum_amount=Decimal("15.00"), declared_value_cap=Decimal("10.00")),
    ]
    with pytest.raises(ValueError):
        allocate_claim_pro_rata(Decimal("20.00"), shares)
