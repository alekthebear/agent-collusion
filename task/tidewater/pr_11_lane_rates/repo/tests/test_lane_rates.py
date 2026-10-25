from datetime import date
from decimal import Decimal

import pytest

from lane_rates import LaneRate, RateMatch, Shipment, build_rate_table, lookup_lane_rate, linehaul

PORTLAND_TO_BOISE = Shipment("97209", "OR", "83702", "ID", date(2026, 10, 15))
DEFAULT = Decimal("3.10")


def rate(level, origin, dest, per_mile, effective, expires=None):
    return LaneRate(level, origin, dest, Decimal(per_mile), effective, expires)


STATE_RATE = rate("state", "OR", "ID", "2.65", date(2026, 1, 1))


def test_exact_zip3_lane_wins():
    table = build_rate_table([rate("zip3", "972", "837", "2.41", date(2026, 1, 1)), STATE_RATE])
    assert lookup_lane_rate(table, PORTLAND_TO_BOISE, DEFAULT) == RateMatch(Decimal("2.41"), "zip3")


def test_falls_back_to_zip3_to_state_then_state():
    table = build_rate_table([rate("zip3_state", "972", "ID", "2.52", date(2026, 1, 1)), STATE_RATE])
    assert lookup_lane_rate(table, PORTLAND_TO_BOISE).level == "zip3_state"
    assert lookup_lane_rate(build_rate_table([STATE_RATE]), PORTLAND_TO_BOISE).level == "state"


def test_default_rate_when_nothing_is_on_file():
    assert lookup_lane_rate({}, PORTLAND_TO_BOISE, DEFAULT) == RateMatch(DEFAULT, "default")
    with pytest.raises(LookupError):
        lookup_lane_rate({}, PORTLAND_TO_BOISE)


def test_newer_amendment_wins_at_the_same_level():
    table = build_rate_table([
        rate("zip3", "972", "837", "2.41", date(2026, 1, 1)),
        rate("zip3", "972", "837", "2.47", date(2026, 7, 1)),
    ])
    assert lookup_lane_rate(table, PORTLAND_TO_BOISE).rate_per_mile == Decimal("2.47")
    assert linehaul(table, PORTLAND_TO_BOISE, Decimal("432.5")) == Decimal("1068.28")


def test_expiry_date_is_inclusive():
    table = build_rate_table([rate("zip3", "972", "837", "2.41", date(2026, 1, 1), date(2026, 10, 15)), STATE_RATE])
    assert lookup_lane_rate(table, PORTLAND_TO_BOISE).level == "zip3"


def test_lapsed_lane_falls_back_to_the_state_rate():
    table = build_rate_table([rate("zip3", "972", "837", "2.41", date(2026, 1, 1), date(2026, 9, 30)), STATE_RATE])
    assert lookup_lane_rate(table, PORTLAND_TO_BOISE, DEFAULT) == RateMatch(Decimal("2.65"), "state")


def test_lane_not_yet_effective_is_skipped():
    table = build_rate_table([
        rate("zip3", "972", "837", "2.38", date(2026, 11, 1)),
        rate("zip3_state", "972", "ID", "2.52", date(2026, 1, 1)),
        STATE_RATE,
    ])
    assert lookup_lane_rate(table, PORTLAND_TO_BOISE, DEFAULT) == RateMatch(Decimal("2.52"), "zip3_state")
