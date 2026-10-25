"""Overage-shortage-damage variance for settled shipment quantities.

Operations records four quantity checkpoints for many LTL and pool shipments: the
units tendered by the shipper, units physically loaded on the trailer, units
received by the consignee, and units noted on exception paperwork as damaged.
This module converts those counts into a single settlement variance under these
business rules:

* Variance is measured against the tendered quantity.
* Delivered units are reduced by damaged units because damaged freight is not
  considered cleanly delivered for claim tolerance.
* Clean delivery cannot exceed loaded units when a load was tendered. On zero-
  tender cleanups, surprise delivered units are counted as overage as entered.
* A small shortage or overage is ignored when it is within the smaller of the
  absolute unit tolerance and the percentage tolerance for the shipment.
* For large shipments, that computed tolerance may not exceed the large-shipment
  cap.
* Shortage variance is negative, overage variance is positive, and exact or
  tolerated results return 0.00 units.
* If every tendered unit is marked damaged, the full tender is treated as loss
  even if delivered quantity was entered the same.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
DEFAULT_ABSOLUTE_TOLERANCE = Decimal("1.00")
DEFAULT_PERCENT_TOLERANCE = Decimal("0.005")
LARGE_SHIPMENT_UNITS = Decimal("500")
LARGE_SHIPMENT_CAP = Decimal("2.00")


@dataclass(frozen=True)
class ShipmentQuantities:
    tendered_units: Decimal
    loaded_units: Decimal
    delivered_units: Decimal
    damaged_units: Decimal = Decimal("0")


@dataclass(frozen=True)
class VarianceTerms:
    absolute_tolerance_units: Decimal = DEFAULT_ABSOLUTE_TOLERANCE
    percent_tolerance: Decimal = DEFAULT_PERCENT_TOLERANCE
    large_shipment_threshold: Decimal = LARGE_SHIPMENT_UNITS
    large_shipment_tolerance_cap: Decimal = LARGE_SHIPMENT_CAP


def _validate(qty: ShipmentQuantities, terms: VarianceTerms) -> None:
    values = {
        "tendered_units": qty.tendered_units,
        "loaded_units": qty.loaded_units,
        "delivered_units": qty.delivered_units,
        "damaged_units": qty.damaged_units,
    }
    for name, value in values.items():
        if value < 0:
            raise ValueError(f"{name} cannot be negative: {value}")
    if qty.loaded_units > qty.tendered_units:
        raise ValueError("loaded_units cannot exceed tendered_units")
    if qty.damaged_units > qty.delivered_units:
        raise ValueError("damaged_units cannot exceed delivered_units")
    if terms.absolute_tolerance_units < 0 or terms.percent_tolerance < 0:
        raise ValueError("tolerances cannot be negative")


def _quantize_units(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _effective_tolerance(tendered_units: Decimal, terms: VarianceTerms) -> Decimal:
    percent_based = tendered_units * terms.percent_tolerance
    tolerance = max(terms.absolute_tolerance_units, percent_based)
    if tendered_units >= terms.large_shipment_threshold:
        tolerance = min(tolerance, terms.large_shipment_tolerance_cap)
    return _quantize_units(tolerance)


def _clean_delivered_units(qty: ShipmentQuantities) -> Decimal:
    if qty.damaged_units >= qty.tendered_units and qty.tendered_units > 0:
        return Decimal("0")
    clean = qty.delivered_units - qty.damaged_units
    if clean < 0:
        clean = Decimal("0")
    if qty.tendered_units == 0:
        return clean
    return min(clean, qty.loaded_units)


def calculate_osd_variance(
    qty: ShipmentQuantities, terms: VarianceTerms = VarianceTerms()
) -> Decimal:
    """Net OSD variance in units, rounded to hundredths.

    Positive values mean overage versus tender. Negative values mean shortage.
    Variances whose absolute value is within tolerance return 0.00.

    >>> calculate_osd_variance(ShipmentQuantities(Decimal("100"), Decimal("100"), Decimal("99.7")))
    Decimal('0.00')
    """
    _validate(qty, terms)
    if qty.tendered_units == 0:
        return _quantize_units(_clean_delivered_units(qty))

    clean_delivered = _clean_delivered_units(qty)
    raw_variance = _quantize_units(clean_delivered - qty.tendered_units)
    if raw_variance == Decimal("0.00"):
        return raw_variance

    tolerance = _effective_tolerance(qty.tendered_units, terms)
    if abs(raw_variance) <= tolerance:
        return Decimal("0.00")
    return raw_variance
