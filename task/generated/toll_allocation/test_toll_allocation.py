from decimal import Decimal

import pytest

from toll_allocation import (
    TollAllocationTerms,
    TollSegment,
    allocate_toll_costs,
)


def test_loaded_segment_bills_customer_by_default():
    segs = [TollSegment(toll=Decimal("12.00"), miles=Decimal("20"), loaded=True)]
    result = allocate_toll_costs(segs)
    assert result.customer == Decimal("12.00")
    assert result.driver == Decimal("0.00")
    assert result.carrier == Decimal("0.00")


def test_empty_segment_can_split_with_driver():
    segs = [TollSegment(toll=Decimal("10.00"), miles=Decimal("15"), loaded=False)]
    terms = TollAllocationTerms(driver_empty_share=Decimal("0.25"))
    result = allocate_toll_costs(segs, terms)
    assert result.customer == Decimal("0.00")
    assert result.driver == Decimal("2.50")
    assert result.carrier == Decimal("7.50")


def test_short_loaded_segment_is_treated_like_empty():
    segs = [TollSegment(toll=Decimal("9.00"), miles=Decimal("7.99"), loaded=True)]
    terms = TollAllocationTerms(driver_empty_share=Decimal("0.50"))
    result = allocate_toll_costs(segs, terms)
    assert result.customer == Decimal("0.00")
    assert result.driver == Decimal("4.50")
    assert result.carrier == Decimal("4.50")


def test_loaded_segment_at_threshold_is_customer_facing():
    segs = [TollSegment(toll=Decimal("9.00"), miles=Decimal("8.00"), loaded=True)]
    result = allocate_toll_costs(segs)
    assert result.customer == Decimal("9.00")
    assert result.driver == Decimal("0.00")
    assert result.carrier == Decimal("0.00")


def test_high_cost_loaded_segment_caps_customer_share():
    segs = [TollSegment(toll=Decimal("40.00"), miles=Decimal("50"), loaded=True)]
    terms = TollAllocationTerms(customer_loaded_share=Decimal("1.00"))
    result = allocate_toll_costs(segs, terms)
    assert result.customer == Decimal("34.00")
    assert result.driver == Decimal("0.00")
    assert result.carrier == Decimal("6.00")


def test_high_cost_threshold_itself_does_not_trigger_cap():
    segs = [TollSegment(toll=Decimal("35.00"), miles=Decimal("50"), loaded=True)]
    terms = TollAllocationTerms(customer_loaded_share=Decimal("1.00"))
    result = allocate_toll_costs(segs, terms)
    assert result.customer == Decimal("35.00")
    assert result.driver == Decimal("0.00")
    assert result.carrier == Decimal("0.00")


def test_waived_zero_toll_and_zero_miles_segments_are_ignored():
    segs = [
        TollSegment(toll=Decimal("5.00"), miles=Decimal("12"), loaded=True, waived=True),
        TollSegment(toll=Decimal("0.00"), miles=Decimal("12"), loaded=False),
        TollSegment(toll=Decimal("8.00"), miles=Decimal("0.00"), loaded=True),
    ]
    result = allocate_toll_costs(segs)
    assert result.customer == Decimal("0.00")
    assert result.driver == Decimal("0.00")
    assert result.carrier == Decimal("0.00")


def test_rounding_is_half_up_on_segment_split():
    segs = [TollSegment(toll=Decimal("10.01"), miles=Decimal("30"), loaded=False)]
    terms = TollAllocationTerms(driver_empty_share=Decimal("0.50"))
    result = allocate_toll_costs(segs, terms)
    assert result.customer == Decimal("0.00")
    assert result.driver == Decimal("5.01")
    assert result.carrier == Decimal("5.00")


def test_negative_values_are_rejected():
    with pytest.raises(ValueError):
        allocate_toll_costs([TollSegment(toll=Decimal("-1.00"), miles=Decimal("5"), loaded=True)])
    with pytest.raises(ValueError):
        allocate_toll_costs([TollSegment(toll=Decimal("1.00"), miles=Decimal("-5"), loaded=True)])
    with pytest.raises(ValueError):
        allocate_toll_costs([], TollAllocationTerms(customer_loaded_share=Decimal("1.10")))
