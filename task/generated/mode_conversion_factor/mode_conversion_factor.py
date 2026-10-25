"""Equivalent rating factors for converting between freight pricing modes.

Operations normalizes customer rates across truckload, LTL, drayage, and flatbed so
analytics can compare bids on a common basis. The conversion here returns a factor
that multiplies the source mode's amount into an equivalent target-mode amount.

Business rules:
- Base factors are configured per source/target mode pair.
- Weight, distance, and stop count slightly adjust the factor within narrow bands.
- Residential delivery only affects LTL destinations.
- Hazmat applies a small uplift except on drayage, where local port tariffs already
  include most handling.
- Cross-border moves add friction on truckload and flatbed conversions.
- Very short drayage moves under 25 miles use a local minimum factor.
- Flatbed with over-dimensional freight adds an extra uplift.
- Final factors are rounded half up to four decimals and never below 0.2500.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

FOUR_PLACES = Decimal("0.0001")
MIN_FACTOR = Decimal("0.2500")

_BASE_FACTORS = {
    ("truckload", "ltl"): Decimal("1.1800"),
    ("truckload", "drayage"): Decimal("0.7600"),
    ("truckload", "flatbed"): Decimal("1.1200"),
    ("ltl", "truckload"): Decimal("0.8500"),
    ("ltl", "drayage"): Decimal("0.6400"),
    ("ltl", "flatbed"): Decimal("1.0500"),
    ("drayage", "truckload"): Decimal("1.3100"),
    ("drayage", "ltl"): Decimal("1.4200"),
    ("drayage", "flatbed"): Decimal("1.2700"),
    ("flatbed", "truckload"): Decimal("0.9100"),
    ("flatbed", "ltl"): Decimal("1.0900"),
    ("flatbed", "drayage"): Decimal("0.7000"),
}


@dataclass(frozen=True)
class ConversionRequest:
    source_mode: str
    target_mode: str
    weight_lb: int
    distance_miles: int
    stops: int = 2
    residential: bool = False
    hazmat: bool = False
    cross_border: bool = False
    overdimensional: bool = False


@dataclass(frozen=True)
class ConversionTerms:
    heavy_weight_threshold_lb: int = 30000
    long_haul_threshold_miles: int = 1000
    stop_surcharge_per_extra_stop: Decimal = Decimal("0.0150")
    max_stop_surcharge: Decimal = Decimal("0.0600")
    short_drayage_max_miles: int = 25
    short_drayage_factor: Decimal = Decimal("0.5800")


def _validate(req: ConversionRequest) -> None:
    modes = {"truckload", "ltl", "drayage", "flatbed"}
    if req.source_mode not in modes or req.target_mode not in modes:
        raise ValueError("unsupported mode")
    if req.source_mode == req.target_mode:
        raise ValueError("source and target modes must differ")
    if req.weight_lb <= 0 or req.distance_miles <= 0:
        raise ValueError("weight and distance must be positive")
    if req.stops < 1:
        raise ValueError("stops must be at least 1")


def _base_factor(req: ConversionRequest, terms: ConversionTerms) -> Decimal:
    if req.source_mode == "drayage" and req.distance_miles <= terms.short_drayage_max_miles:
        if req.target_mode == "truckload":
            return terms.short_drayage_factor
    return _BASE_FACTORS[(req.source_mode, req.target_mode)]


def _weight_adjustment(req: ConversionRequest, terms: ConversionTerms) -> Decimal:
    if req.target_mode == "ltl":
        if req.weight_lb < 5000:
            return Decimal("0.0800")
        if req.weight_lb > 20000:
            return Decimal("-0.0500")
    if req.weight_lb >= terms.heavy_weight_threshold_lb and req.target_mode in {"truckload", "flatbed"}:
        return Decimal("0.0400")
    return Decimal("0.0000")


def _distance_adjustment(req: ConversionRequest, terms: ConversionTerms) -> Decimal:
    if req.distance_miles < 50 and req.target_mode == "ltl":
        return Decimal("0.0600")
    if req.distance_miles >= terms.long_haul_threshold_miles and req.target_mode in {"truckload", "flatbed"}:
        return Decimal("-0.0300")
    return Decimal("0.0000")


def _accessorial_adjustment(req: ConversionRequest, terms: ConversionTerms) -> Decimal:
    adj = Decimal("0.0000")
    extra_stops = max(req.stops - 2, 0)
    stop_adj = terms.stop_surcharge_per_extra_stop * extra_stops
    if stop_adj > terms.max_stop_surcharge:
        stop_adj = terms.max_stop_surcharge
    adj += stop_adj
    if req.residential and req.target_mode == "ltl":
        adj += Decimal("0.0450")
    if req.hazmat:
        adj += Decimal("0.0100") if req.target_mode == "drayage" else Decimal("0.0250")
    if req.cross_border and req.target_mode in {"truckload", "flatbed"}:
        adj += Decimal("0.0350")
    if req.overdimensional and req.target_mode == "flatbed":
        adj += Decimal("0.0700")
    return adj


def calculate_mode_conversion_factor(
    req: ConversionRequest, terms: ConversionTerms = ConversionTerms()
) -> Decimal:
    """Return the equivalent factor from source mode pricing to target mode pricing."""
    _validate(req)
    factor = _base_factor(req, terms)
    factor += _weight_adjustment(req, terms)
    factor += _distance_adjustment(req, terms)
    factor += _accessorial_adjustment(req, terms)
    if factor < MIN_FACTOR:
        factor = MIN_FACTOR
    return factor.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
