"""Reserve release calculations for carrier settlements.

Operations keeps a cash reserve against each carrier to cover short-pay disputes,
late lumper receipts, cargo claims, and chargeback corrections. At settlement time,
we release only the portion that is old enough and not blocked by business holds.

Business rules used by Tidewater settlement:
- Reserve buckets age from the original settlement date.
- Amounts younger than 30 days are not releasable.
- From 30 through 59 days, at most 50% of the aged amount may release.
- At 60 days and older, up to 100% of the aged amount may release.
- If the carrier is on claim hold, no release occurs.
- If unresolved claim exposure exceeds $500.00, no release occurs.
- Otherwise, unresolved claim exposure up to $500.00 reduces the release dollar for
  dollar.
- We always retain a minimum ending reserve balance. Preferred carriers retain
  $250.00; standard carriers retain $1,000.00.
- If the carrier had a payment return within 90 days, retain an extra $300.00.
- Negative or zero available reserve releases as $0.00.
- Results are rounded to the cent using half-up rounding.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
YOUNG_DAYS = 30
FULL_DAYS = 60
CLAIM_BLOCK_THRESHOLD = Decimal("500.00")
STANDARD_FLOOR = Decimal("1000.00")
PREFERRED_FLOOR = Decimal("250.00")
RETURN_PENALTY_FLOOR = Decimal("300.00")


@dataclass(frozen=True)
class ReserveBucket:
    amount: Decimal
    settled_on: date


@dataclass(frozen=True)
class ReserveReleaseContext:
    as_of: date
    unresolved_claim_exposure: Decimal = Decimal("0.00")
    claim_hold: bool = False
    preferred_carrier: bool = False
    recent_payment_return: bool = False


def _validate_bucket(bucket: ReserveBucket, as_of: date) -> None:
    if bucket.amount < Decimal("0.00"):
        raise ValueError(f"bucket amount {bucket.amount} cannot be negative")
    if bucket.settled_on > as_of:
        raise ValueError(f"settled_on {bucket.settled_on} is after as_of {as_of}")


def _validate_context(context: ReserveReleaseContext) -> None:
    if context.unresolved_claim_exposure < Decimal("0.00"):
        raise ValueError("unresolved_claim_exposure cannot be negative")


def _aged_release_ratio(age_days: int) -> Decimal:
    if age_days < YOUNG_DAYS:
        return Decimal("0.00")
    if age_days < FULL_DAYS:
        return Decimal("0.50")
    return Decimal("1.00")


def _bucket_releasable(bucket: ReserveBucket, as_of: date) -> Decimal:
    age_days = (as_of - bucket.settled_on).days
    ratio = _aged_release_ratio(age_days)
    if ratio == Decimal("0.00"):
        return Decimal("0.00")
    return (bucket.amount * ratio).quantize(CENT, rounding=ROUND_HALF_UP)


def _minimum_retained_balance(context: ReserveReleaseContext) -> Decimal:
    floor = PREFERRED_FLOOR if context.preferred_carrier else STANDARD_FLOOR
    if context.recent_payment_return:
        floor += RETURN_PENALTY_FLOOR
    return floor


def calculate_reserve_release(
    buckets: list[ReserveBucket], context: ReserveReleaseContext
) -> Decimal:
    """Amount of reserve that may be released now.

    The function totals current reserve, computes the aged releasable portion by
    bucket, subtracts eligible claim exposure, and then limits the result so the
    remaining reserve does not fall below the required floor.
    """
    _validate_context(context)
    for bucket in buckets:
        _validate_bucket(bucket, context.as_of)

    if context.claim_hold:
        return Decimal("0.00")
    if context.unresolved_claim_exposure > CLAIM_BLOCK_THRESHOLD:
        return Decimal("0.00")

    total_reserve = sum((bucket.amount for bucket in buckets), Decimal("0.00"))
    aged_available = sum(
        (_bucket_releasable(bucket, context.as_of) for bucket in buckets), Decimal("0.00")
    )
    if aged_available <= Decimal("0.00"):
        return Decimal("0.00")

    after_claims = aged_available - context.unresolved_claim_exposure
    if after_claims <= Decimal("0.00"):
        return Decimal("0.00")

    max_by_floor = total_reserve - _minimum_retained_balance(context)
    if max_by_floor <= Decimal("0.00"):
        return Decimal("0.00")

    release = min(after_claims, max_by_floor)
    return release.quantize(CENT, rounding=ROUND_HALF_UP)
