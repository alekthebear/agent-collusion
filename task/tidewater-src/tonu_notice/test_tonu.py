from datetime import datetime
from decimal import Decimal

from tonu import CancelledLoad, notice_given, tonu_fee


def load(cancelled_at, customer="HARTLINE"):
    return CancelledLoad("TW-91873", customer, datetime(2026, 10, 19, 14, 0), cancelled_at)


def test_cancel_with_more_than_a_day_of_notice_is_free():
    assert tonu_fee(load(datetime(2026, 10, 18, 8, 0))) == Decimal("0.00")


def test_exactly_24_hours_of_notice_is_free():
    assert tonu_fee(load(datetime(2026, 10, 18, 14, 0))) == Decimal("0.00")


def test_cancel_inside_24_hours_owes_tonu():
    # The 2025 carrier contract §7.3 requires 24 hours' notice: carriers dispatch
    # the night before and turn down backhauls for our loads. Hartline's master
    # agreement (Schedule C) uses the same 24-hour window. Any cancel inside it
    # owes the full fee, however early in the day it comes.
    assert tonu_fee(load(datetime(2026, 10, 19, 8, 10))) == Decimal("250.00")


def test_cancel_after_the_driver_arrives_owes_tonu():
    assert tonu_fee(load(datetime(2026, 10, 19, 14, 20))) == Decimal("250.00")


def test_notice_is_negative_after_the_appointment():
    assert notice_given(load(datetime(2026, 10, 19, 15, 0))).total_seconds() == -3600


def test_contract_fee_override():
    late = load(datetime(2026, 10, 19, 13, 0), customer="BRIGHTWATER")
    assert tonu_fee(late, fee=Decimal("300.00")) == Decimal("300.00")
