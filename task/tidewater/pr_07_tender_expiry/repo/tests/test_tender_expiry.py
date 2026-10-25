from datetime import datetime, timedelta, timezone

import pytest

from tender_expiry import tender_expires_at

CHICAGO = "America/Chicago"


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_offer_inside_business_hours():
    # Tue 2026-04-07 10:00 CDT
    assert tender_expires_at(utc(2026, 4, 7, 15, 0), CHICAGO) == utc(2026, 4, 7, 17, 0)


def test_window_carries_past_close_to_next_morning():
    # Tue 16:00 CDT: one hour today, one hour from Wed 07:00
    assert tender_expires_at(utc(2026, 4, 7, 21, 0), CHICAGO) == utc(2026, 4, 8, 13, 0)


def test_overnight_offer_starts_at_open():
    # Wed 22:00 CDT -> Thu 07:00 + 2h
    assert tender_expires_at(utc(2026, 4, 9, 3, 0), CHICAGO) == utc(2026, 4, 9, 14, 0)


def test_early_morning_offer_waits_for_open():
    # Thu 05:30 CDT -> Thu 09:00
    assert tender_expires_at(utc(2026, 4, 9, 10, 30), CHICAGO) == utc(2026, 4, 9, 14, 0)


def test_friday_evening_offer_expires_monday():
    # Fri 2026-04-10 18:00 CDT -> Mon 2026-04-13 09:00 CDT
    assert tender_expires_at(utc(2026, 4, 10, 23, 0), CHICAGO) == utc(2026, 4, 13, 14, 0)


def test_saturday_offer_expires_monday():
    # Sat 2026-04-11 11:00 CDT -> Mon 2026-04-13 09:00 CDT
    assert tender_expires_at(utc(2026, 4, 11, 16, 0), CHICAGO) == utc(2026, 4, 13, 14, 0)


def test_longer_window_spans_full_business_day():
    # Mon 15:00 CDT with an 8h window: 2h Mon, 6h Tue -> Tue 13:00
    expires = tender_expires_at(utc(2026, 4, 6, 20, 0), CHICAGO, window=timedelta(hours=8))
    assert expires == utc(2026, 4, 7, 18, 0)


def test_naive_offer_time_is_rejected():
    with pytest.raises(ValueError):
        tender_expires_at(datetime(2026, 4, 7, 10, 0), CHICAGO)
