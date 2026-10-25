from datetime import date
from decimal import Decimal

import pytest

from reserve_release import (
    ReserveBucket,
    ReserveReleaseContext,
    calculate_reserve_release,
)


def test_younger_than_30_days_does_not_release():
    buckets = [ReserveBucket(amount=Decimal("1500.00"), settled_on=date(2026, 3, 2))]
    context = ReserveReleaseContext(as_of=date(2026, 3, 31))
    assert calculate_reserve_release(buckets, context) == Decimal("0.00")


def test_exactly_30_days_releases_half_of_bucket_subject_to_floor():
    buckets = [ReserveBucket(amount=Decimal("3000.00"), settled_on=date(2026, 3, 1))]
    context = ReserveReleaseContext(as_of=date(2026, 3, 31))
    assert calculate_reserve_release(buckets, context) == Decimal("1500.00")


def test_exactly_60_days_releases_full_bucket_subject_to_floor():
    buckets = [ReserveBucket(amount=Decimal("1800.00"), settled_on=date(2026, 1, 30))]
    context = ReserveReleaseContext(as_of=date(2026, 3, 31))
    assert calculate_reserve_release(buckets, context) == Decimal("800.00")


def test_claim_hold_blocks_all_release():
    buckets = [ReserveBucket(amount=Decimal("5000.00"), settled_on=date(2026, 1, 1))]
    context = ReserveReleaseContext(as_of=date(2026, 3, 31), claim_hold=True)
    assert calculate_reserve_release(buckets, context) == Decimal("0.00")


def test_claim_exposure_over_threshold_blocks_release():
    buckets = [ReserveBucket(amount=Decimal("5000.00"), settled_on=date(2026, 1, 1))]
    context = ReserveReleaseContext(
        as_of=date(2026, 3, 31), unresolved_claim_exposure=Decimal("500.01")
    )
    assert calculate_reserve_release(buckets, context) == Decimal("0.00")


def test_claim_exposure_at_threshold_reduces_dollar_for_dollar():
    buckets = [ReserveBucket(amount=Decimal("2000.00"), settled_on=date(2026, 1, 1))]
    context = ReserveReleaseContext(
        as_of=date(2026, 3, 31), unresolved_claim_exposure=Decimal("500.00")
    )
    assert calculate_reserve_release(buckets, context) == Decimal("1000.00")


def test_preferred_carrier_has_lower_minimum_balance():
    buckets = [ReserveBucket(amount=Decimal("800.00"), settled_on=date(2026, 1, 1))]
    context = ReserveReleaseContext(as_of=date(2026, 3, 31), preferred_carrier=True)
    assert calculate_reserve_release(buckets, context) == Decimal("550.00")


def test_recent_payment_return_increases_retention_floor():
    buckets = [ReserveBucket(amount=Decimal("2000.00"), settled_on=date(2026, 1, 1))]
    context = ReserveReleaseContext(as_of=date(2026, 3, 31), recent_payment_return=True)
    assert calculate_reserve_release(buckets, context) == Decimal("700.00")


def test_mixed_buckets_and_rounding_produce_exact_cents():
    buckets = [
        ReserveBucket(amount=Decimal("1000.01"), settled_on=date(2026, 3, 1)),
        ReserveBucket(amount=Decimal("800.00"), settled_on=date(2026, 1, 1)),
        ReserveBucket(amount=Decimal("500.00"), settled_on=date(2026, 3, 15)),
    ]
    context = ReserveReleaseContext(as_of=date(2026, 3, 31))
    assert calculate_reserve_release(buckets, context) == Decimal("1300.01")


def test_negative_bucket_amount_is_rejected():
    buckets = [ReserveBucket(amount=Decimal("-1.00"), settled_on=date(2026, 1, 1))]
    context = ReserveReleaseContext(as_of=date(2026, 3, 31))
    with pytest.raises(ValueError):
        calculate_reserve_release(buckets, context)
