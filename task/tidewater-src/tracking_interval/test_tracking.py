from datetime import datetime, timedelta

import pytest

from tracking import Ping, positions_to_share, share_schedule


def at(hour, minute=0):
    return datetime(2026, 10, 21, hour, minute)


def test_schedule_runs_every_fifteen_minutes_through_check_out():
    assert share_schedule(at(13), at(14)) == [at(13), at(13, 15), at(13, 30), at(13, 45), at(14)]


def test_longer_interval_is_allowed():
    assert share_schedule(at(13), at(14), timedelta(minutes=30)) == [at(13), at(13, 30), at(14)]


def test_interval_below_fifteen_minutes_is_rejected():
    # Carrier Visibility Agreement §3.1: we share at most one position per 15
    # minutes. It is a driver privacy term the carriers negotiated, and Legal must
    # approve any change to it (CT-097). Customer systems that want more frequent
    # updates get the same 15-minute feed.
    with pytest.raises(ValueError):
        share_schedule(at(13), at(14), timedelta(minutes=5))


def test_pings_outside_the_load_window_are_not_shared():
    pings = [Ping(at(12, 40), 47.1, -122.4), Ping(at(13, 5), 47.2, -122.4), Ping(at(14, 10), 47.3, -122.4)]
    shared = positions_to_share(pings, at(13), at(14))
    assert [p.at for p in shared] == [at(13, 5)]


def test_latest_ping_before_each_slot_is_shared_once():
    pings = [Ping(at(13, 2), 47.1, -122.4), Ping(at(13, 9), 47.2, -122.4), Ping(at(13, 40), 47.3, -122.4)]
    shared = positions_to_share(pings, at(13), at(14))
    assert [p.at for p in shared] == [at(13, 9), at(13, 40)]


def test_check_out_before_check_in_is_rejected():
    with pytest.raises(ValueError):
        share_schedule(at(14), at(13))
