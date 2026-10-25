from decimal import Decimal

import pytest

from edi_997_ack_status import AckCounts, AckPolicy, ControlBalance, calculate_edi_997_ack_status


def test_balanced_all_accepted_is_accepted():
    counts = AckCounts(accepted_count=12, rejected_count=0, included_count=12)
    control = ControlBalance(group_control_sent=4102, group_control_received=4102)
    assert calculate_edi_997_ack_status(counts, control) == "ACCEPTED"


def test_balanced_mix_of_accepts_and_rejects_is_partial():
    counts = AckCounts(accepted_count=7, rejected_count=2, included_count=9)
    control = ControlBalance(group_control_sent=88, group_control_received=88)
    assert calculate_edi_997_ack_status(counts, control) == "PARTIALLY_ACCEPTED"


def test_balanced_all_rejected_is_rejected():
    counts = AckCounts(accepted_count=0, rejected_count=4, included_count=4)
    control = ControlBalance(group_control_sent=900, group_control_received=900)
    assert calculate_edi_997_ack_status(counts, control) == "REJECTED"


def test_zero_included_is_empty():
    counts = AckCounts(accepted_count=0, rejected_count=0, included_count=0)
    control = ControlBalance(group_control_sent=1, group_control_received=1)
    assert calculate_edi_997_ack_status(counts, control) == "EMPTY"


def test_positive_included_with_no_classification_is_received_not_classified():
    counts = AckCounts(accepted_count=0, rejected_count=0, included_count=3)
    control = ControlBalance(group_control_sent=55, group_control_received=55)
    assert calculate_edi_997_ack_status(counts, control) == "RECEIVED_NOT_CLASSIFIED"


def test_control_gap_above_threshold_is_control_mismatch():
    counts = AckCounts(accepted_count=5, rejected_count=0, included_count=5)
    control = ControlBalance(group_control_sent=1000, group_control_received=1002, allowed_control_gap=1)
    assert calculate_edi_997_ack_status(counts, control) == "CONTROL_MISMATCH"


def test_lenient_partner_ignores_control_mismatch():
    counts = AckCounts(accepted_count=5, rejected_count=0, included_count=5)
    control = ControlBalance(group_control_sent=1000, group_control_received=1009, lenient_partner=True)
    assert calculate_edi_997_ack_status(counts, control) == "ACCEPTED"


def test_overage_within_tolerance_is_allowed():
    counts = AckCounts(accepted_count=98, rejected_count=0, included_count=100)
    control = ControlBalance(group_control_sent=77, group_control_received=77)
    policy = AckPolicy(overage_tolerance=Decimal("0.0200"))
    assert calculate_edi_997_ack_status(counts, control, policy) == "ACCEPTED"


def test_rounded_overage_above_tolerance_is_count_mismatch():
    counts = AckCounts(accepted_count=9950, rejected_count=0, included_count=10000)
    control = ControlBalance(group_control_sent=77, group_control_received=77)
    policy = AckPolicy(overage_tolerance=Decimal("0.0049"))
    assert calculate_edi_997_ack_status(counts, control, policy) == "COUNT_MISMATCH"


def test_negative_count_is_rejected():
    counts = AckCounts(accepted_count=-1, rejected_count=0, included_count=0)
    control = ControlBalance(group_control_sent=1, group_control_received=1)
    with pytest.raises(ValueError):
        calculate_edi_997_ack_status(counts, control)
