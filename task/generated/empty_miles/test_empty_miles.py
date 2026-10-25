from decimal import Decimal

import pytest

from empty_miles import LoadContext, LoadedSegment, calculate_empty_miles


def test_start_deadhead_at_threshold_is_ignored():
    ctx = LoadContext(start_deadhead_miles=Decimal("7.0"))
    segs = (LoadedSegment(loaded_miles=Decimal("120")),)
    assert calculate_empty_miles(ctx, segs) == Decimal("0")


def test_start_deadhead_above_threshold_counts_and_rounds_half_up():
    ctx = LoadContext(start_deadhead_miles=Decimal("7.5"))
    segs = (LoadedSegment(loaded_miles=Decimal("120")),)
    assert calculate_empty_miles(ctx, segs) == Decimal("8")


def test_reposition_gap_at_threshold_is_ignored():
    ctx = LoadContext(start_deadhead_miles=Decimal("0"))
    segs = (
        LoadedSegment(loaded_miles=Decimal("80"), reposition_miles_after=Decimal("7.0")),
        LoadedSegment(loaded_miles=Decimal("90")),
    )
    assert calculate_empty_miles(ctx, segs) == Decimal("0")


def test_team_driver_discount_applies_only_to_reposition():
    ctx = LoadContext(start_deadhead_miles=Decimal("12"), team_driver=True)
    segs = (
        LoadedSegment(loaded_miles=Decimal("100"), reposition_miles_after=Decimal("10")),
        LoadedSegment(loaded_miles=Decimal("50")),
    )
    assert calculate_empty_miles(ctx, segs) == Decimal("21")


def test_hazmat_adds_buffer_to_each_counted_empty_leg():
    ctx = LoadContext(start_deadhead_miles=Decimal("8"), hazardous=True)
    segs = (
        LoadedSegment(loaded_miles=Decimal("100"), reposition_miles_after=Decimal("9")),
        LoadedSegment(loaded_miles=Decimal("60")),
    )
    assert calculate_empty_miles(ctx, segs) == Decimal("22")


def test_cancelled_segment_counts_half_of_approach_miles():
    ctx = LoadContext(start_deadhead_miles=Decimal("0"))
    segs = (
        LoadedSegment(
            loaded_miles=Decimal("100"),
            reposition_miles_after=Decimal("10"),
            cancelled_after_dispatch=True,
        ),
        LoadedSegment(loaded_miles=Decimal("40")),
    )
    assert calculate_empty_miles(ctx, segs) == Decimal("5")


def test_border_crossing_adds_admin_miles_once_when_any_empty_exists():
    ctx = LoadContext(start_deadhead_miles=Decimal("8"), border_crossing=True)
    segs = (LoadedSegment(loaded_miles=Decimal("100")),)
    assert calculate_empty_miles(ctx, segs) == Decimal("11")


def test_border_crossing_does_not_add_admin_miles_when_no_empty_miles_count():
    ctx = LoadContext(start_deadhead_miles=Decimal("6"), border_crossing=True)
    segs = (LoadedSegment(loaded_miles=Decimal("100")),)
    assert calculate_empty_miles(ctx, segs) == Decimal("0")


def test_negative_start_deadhead_is_rejected():
    ctx = LoadContext(start_deadhead_miles=Decimal("-1"))
    segs = (LoadedSegment(loaded_miles=Decimal("100")),)
    with pytest.raises(ValueError):
        calculate_empty_miles(ctx, segs)


def test_segment_loaded_miles_must_be_positive():
    ctx = LoadContext(start_deadhead_miles=Decimal("0"))
    segs = (LoadedSegment(loaded_miles=Decimal("0")),)
    with pytest.raises(ValueError):
        calculate_empty_miles(ctx, segs)
