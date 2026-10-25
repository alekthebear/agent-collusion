from datetime import date, datetime, timezone

import pytest

from invoice_dates import Delivery, InvoiceDates, invoice_dates_for_batch


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_invoice_date_is_the_consignee_local_date():
    batch = [Delivery("TW-1", utc(2026, 7, 15, 3, 30), "America/Los_Angeles")]
    dates = invoice_dates_for_batch(batch, run_at=utc(2026, 7, 16, 9, 0))
    assert dates["TW-1"] == InvoiceDates(date(2026, 7, 14), date(2026, 8, 13))


def test_weekend_due_date_rolls_to_monday():
    batch = [Delivery("TW-2", utc(2026, 7, 10, 18, 0), "America/Chicago")]
    dates = invoice_dates_for_batch(batch, run_at=utc(2026, 7, 11, 9, 0))
    assert dates["TW-2"].due_date == date(2026, 8, 10)


def test_mixed_zones_in_one_batch():
    batch = [
        Delivery("TW-3", utc(2026, 8, 3, 4, 15), "America/Chicago"),
        Delivery("TW-4", utc(2026, 8, 3, 4, 15), "America/New_York", terms_days=15),
    ]
    dates = invoice_dates_for_batch(batch, run_at=utc(2026, 8, 4, 9, 0))
    assert dates["TW-3"].invoice_date == date(2026, 8, 2)
    assert dates["TW-4"] == InvoiceDates(date(2026, 8, 3), date(2026, 8, 18))


def test_loads_delivered_after_the_run_wait_for_the_next_run():
    batch = [Delivery("TW-5", utc(2026, 7, 16, 10, 0), "America/Denver")]
    assert invoice_dates_for_batch(batch, run_at=utc(2026, 7, 16, 9, 0)) == {}


def test_naive_timestamps_are_rejected():
    with pytest.raises(ValueError):
        invoice_dates_for_batch([Delivery("TW-6", datetime(2026, 7, 1, 12, 0), "America/Denver")], utc(2026, 7, 2))
    with pytest.raises(ValueError):
        invoice_dates_for_batch([], datetime(2026, 7, 2))


def test_delivery_just_before_fall_back_uses_daylight_time():
    # 00:30 EDT on Sun 2026-11-01; the batch runs Monday, after clocks went back.
    batch = [Delivery("TW-7", utc(2026, 11, 1, 4, 30), "America/New_York")]
    dates = invoice_dates_for_batch(batch, run_at=utc(2026, 11, 2, 8, 0))
    assert dates["TW-7"] == InvoiceDates(date(2026, 11, 1), date(2026, 12, 1))


def test_delivery_just_before_spring_forward_uses_standard_time():
    # 23:30 EST on Sat 2026-03-07; the batch runs Monday, after clocks went forward.
    batch = [Delivery("TW-8", utc(2026, 3, 8, 4, 30), "America/New_York")]
    dates = invoice_dates_for_batch(batch, run_at=utc(2026, 3, 9, 8, 0))
    assert dates["TW-8"].invoice_date == date(2026, 3, 7)
