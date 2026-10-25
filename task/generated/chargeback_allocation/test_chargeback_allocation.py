from decimal import Decimal

import pytest

from chargeback_allocation import Allocation, Chargeback, LoadShare, allocate_chargebacks


def test_single_load_full_fault_allocates_full_amount():
    chargeback = Chargeback(
        amount=Decimal("125.00"),
        reason="penalty",
        loads=(LoadShare("S1", Decimal("1.00"), Decimal("1.00"), Decimal("500.00")),),
    )
    assert allocate_chargebacks(chargeback) == (Allocation("S1", Decimal("125.00")),)


def test_multi_load_attribution_and_fault_split_exactly():
    chargeback = Chargeback(
        amount=Decimal("200.00"),
        reason="penalty",
        loads=(
            LoadShare("A", Decimal("0.60"), Decimal("0.50"), None),
            LoadShare("B", Decimal("0.40"), Decimal("0.25"), None),
        ),
    )
    assert allocate_chargebacks(chargeback) == (
        Allocation("A", Decimal("60.00")),
        Allocation("B", Decimal("20.00")),
    )


def test_unattributed_remainder_is_not_billed():
    chargeback = Chargeback(
        amount=Decimal("100.00"),
        reason="penalty",
        loads=(LoadShare("S1", Decimal("0.80"), Decimal("1.00"), None),),
    )
    assert allocate_chargebacks(chargeback) == (Allocation("S1", Decimal("80.00")),)


def test_service_failure_forgives_first_fifty_per_load_share():
    chargeback = Chargeback(
        amount=Decimal("120.00"),
        reason="service_failure",
        loads=(LoadShare("S1", Decimal("1.00"), Decimal("1.00"), None),),
    )
    assert allocate_chargebacks(chargeback) == (Allocation("S1", Decimal("70.00")),)


def test_cargo_claim_subtracts_salvage_before_fault():
    chargeback = Chargeback(
        amount=Decimal("500.00"),
        reason="cargo_claim",
        salvage_credit=Decimal("80.00"),
        loads=(LoadShare("S1", Decimal("1.00"), Decimal("0.50"), None),),
    )
    assert allocate_chargebacks(chargeback) == (Allocation("S1", Decimal("210.00")),)


def test_fault_below_de_minimis_allocates_nothing():
    chargeback = Chargeback(
        amount=Decimal("999.00"),
        reason="penalty",
        loads=(LoadShare("S1", Decimal("1.00"), Decimal("0.049"), None),),
    )
    assert allocate_chargebacks(chargeback) == ()


def test_cap_limits_noncritical_event_but_critical_ignores_cap():
    load = LoadShare("S1", Decimal("1.00"), Decimal("1.00"), Decimal("150.00"))
    normal = Chargeback(amount=Decimal("220.00"), reason="penalty", loads=(load,))
    critical = Chargeback(amount=Decimal("220.00"), reason="penalty", loads=(load,), critical=True)
    assert allocate_chargebacks(normal) == (Allocation("S1", Decimal("150.00")),)
    assert allocate_chargebacks(critical) == (Allocation("S1", Decimal("220.00")),)


def test_customer_error_allocates_nothing():
    chargeback = Chargeback(
        amount=Decimal("75.00"),
        reason="penalty",
        customer_error=True,
        loads=(LoadShare("S1", Decimal("1.00"), Decimal("1.00"), None),),
    )
    assert allocate_chargebacks(chargeback) == ()


def test_rounds_half_up_at_final_per_load_result():
    chargeback = Chargeback(
        amount=Decimal("10.005"),
        reason="penalty",
        loads=(LoadShare("S1", Decimal("1.00"), Decimal("1.00"), None),),
    )
    assert allocate_chargebacks(chargeback) == (Allocation("S1", Decimal("10.01")),)


def test_total_weight_above_one_is_rejected():
    chargeback = Chargeback(
        amount=Decimal("100.00"),
        reason="penalty",
        loads=(
            LoadShare("A", Decimal("0.70"), Decimal("1.00"), None),
            LoadShare("B", Decimal("0.31"), Decimal("1.00"), None),
        ),
    )
    with pytest.raises(ValueError):
        allocate_chargebacks(chargeback)
