"""Allocate route tolls between customer invoices and carrier internal buckets.

The settlement service uses these rules when a trip's toll feed arrives after dispatch.
Each route is represented as ordered toll segments. Loaded segments are generally billed
to the customer, while empty repositioning is usually absorbed by the carrier. Some
contracts split loaded tolls with the customer paying a percentage and some owner-
operator programs push a share of carrier-responsible tolls to the driver. Segments
with a waived toll or non-positive miles do not allocate any cost. A loaded segment
shorter than a deadhead threshold is treated as a local reposition and billed like an
empty leg. Segment charges are rounded to cents with half-up rounding, and final
bucket totals are also rounded to cents.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
DEFAULT_SHORT_LOADED_MILES = Decimal("8")
DEFAULT_CUSTOMER_SHARE = Decimal("1.00")
DEFAULT_DRIVER_EMPTY_SHARE = Decimal("0.00")
HIGH_COST_THRESHOLD = Decimal("35.00")
HIGH_COST_CUSTOMER_CAP = Decimal("0.85")


@dataclass(frozen=True)
class TollSegment:
    """One tolled route segment for a trip."""

    toll: Decimal
    miles: Decimal
    loaded: bool
    waived: bool = False


@dataclass(frozen=True)
class TollAllocationTerms:
    """Contract and program settings for one trip settlement."""

    customer_loaded_share: Decimal = DEFAULT_CUSTOMER_SHARE
    driver_empty_share: Decimal = DEFAULT_DRIVER_EMPTY_SHARE
    short_loaded_miles: Decimal = DEFAULT_SHORT_LOADED_MILES
    high_cost_customer_cap: Decimal = HIGH_COST_CUSTOMER_CAP


@dataclass(frozen=True)
class TollAllocation:
    customer: Decimal
    driver: Decimal
    carrier: Decimal


def _q(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate_segment(segment: TollSegment) -> None:
    if segment.toll < 0:
        raise ValueError("segment toll cannot be negative")
    if segment.miles < 0:
        raise ValueError("segment miles cannot be negative")


def _validate_terms(terms: TollAllocationTerms) -> None:
    for value, name in (
        (terms.customer_loaded_share, "customer_loaded_share"),
        (terms.driver_empty_share, "driver_empty_share"),
        (terms.high_cost_customer_cap, "high_cost_customer_cap"),
    ):
        if value < 0 or value > 1:
            raise ValueError(f"{name} must be between 0 and 1")
    if terms.short_loaded_miles < 0:
        raise ValueError("short_loaded_miles cannot be negative")


def _is_customer_loaded(segment: TollSegment, terms: TollAllocationTerms) -> bool:
    return segment.loaded and segment.miles >= terms.short_loaded_miles


def _customer_share_for(segment: TollSegment, terms: TollAllocationTerms) -> Decimal:
    share = terms.customer_loaded_share
    if segment.toll > HIGH_COST_THRESHOLD and share > terms.high_cost_customer_cap:
        return terms.high_cost_customer_cap
    return share


def allocate_toll_costs(
    segments: list[TollSegment], terms: TollAllocationTerms = TollAllocationTerms()
) -> TollAllocation:
    """Allocate tolls across customer, driver, and carrier buckets.

    Loaded segments at or above ``short_loaded_miles`` are customer-facing. The customer
    pays ``customer_loaded_share`` of those tolls, except any single segment above
    ``HIGH_COST_THRESHOLD`` is capped at ``high_cost_customer_cap`` to avoid overbilling
    unusually expensive urban crossings. Empty segments and short loaded segments are
    carrier-responsible, with ``driver_empty_share`` optionally charged to the driver.

    >>> from decimal import Decimal
    >>> segs = [TollSegment(toll=Decimal('12.00'), miles=Decimal('20'), loaded=True)]
    >>> allocate_toll_costs(segs)
    TollAllocation(customer=Decimal('12.00'), driver=Decimal('0.00'), carrier=Decimal('0.00'))
    """
    _validate_terms(terms)
    customer = Decimal("0")
    driver = Decimal("0")
    carrier = Decimal("0")

    for segment in segments:
        _validate_segment(segment)
        if segment.waived or segment.toll == 0 or segment.miles == 0:
            continue

        if _is_customer_loaded(segment, terms):
            customer_piece = _q(segment.toll * _customer_share_for(segment, terms))
            carrier_piece = _q(segment.toll - customer_piece)
            customer += customer_piece
            carrier += carrier_piece
        else:
            driver_piece = _q(segment.toll * terms.driver_empty_share)
            carrier_piece = _q(segment.toll - driver_piece)
            driver += driver_piece
            carrier += carrier_piece

    return TollAllocation(customer=_q(customer), driver=_q(driver), carrier=_q(carrier))
