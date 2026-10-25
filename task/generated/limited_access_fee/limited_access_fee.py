"""Limited-access surcharges for freight stops.

A limited-access fee applies when pickup or delivery occurs at locations that are
operationally difficult for a tractor-trailer to service: schools, churches,
construction sites, prisons, military bases, and similar destinations. The rating
service determines a stop's location category from address master data, then calls
``calculate_limited_access_fee`` once per stop.

Business rules:
- No fee applies unless the destination category is marked limited access.
- Fees differ by stop type: delivery uses the full tariff, pickup uses 80%.
- Residential categories do not use this surcharge; they bill elsewhere.
- A stop can receive the limited-access fee only once, even if multiple qualifying
  tags were found while matching the address.
- A remote-area override adds a flat amount, but only when the base fee applies.
- The result is rounded to the nearest cent, half up, and can be capped by tariff.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
DELIVERY_MULTIPLIER = Decimal("1.00")
PICKUP_MULTIPLIER = Decimal("0.80")
REMOTE_ADD_ON = Decimal("18.50")
DEFAULT_CAP = Decimal("185.00")

LIMITED_ACCESS_CATEGORIES = frozenset(
    {
        "airport",
        "campus",
        "church",
        "construction",
        "fairground",
        "farm",
        "military_base",
        "mine",
        "port",
        "prison",
        "school",
        "self_storage",
    }
)
RESIDENTIAL_CATEGORIES = frozenset({"residential", "apartment"})


@dataclass(frozen=True)
class StopFacts:
    category: str
    stop_type: str
    matched_tags: int = 1
    already_applied: bool = False
    remote_area: bool = False


@dataclass(frozen=True)
class LimitedAccessTariff:
    base_fee: Decimal = Decimal("72.00")
    pickup_multiplier: Decimal = PICKUP_MULTIPLIER
    delivery_multiplier: Decimal = DELIVERY_MULTIPLIER
    remote_add_on: Decimal = REMOTE_ADD_ON
    fee_cap: Decimal | None = DEFAULT_CAP


def _validate(stop: StopFacts, tariff: LimitedAccessTariff) -> None:
    if stop.stop_type not in {"pickup", "delivery"}:
        raise ValueError(f"unsupported stop_type: {stop.stop_type}")
    if stop.matched_tags < 0:
        raise ValueError("matched_tags cannot be negative")
    if tariff.base_fee < 0 or tariff.remote_add_on < 0:
        raise ValueError("tariff amounts cannot be negative")
    if tariff.fee_cap is not None and tariff.fee_cap < 0:
        raise ValueError("fee_cap cannot be negative")


def _is_limited_access_category(category: str) -> bool:
    normalized = category.strip().lower()
    if normalized in RESIDENTIAL_CATEGORIES:
        return False
    return normalized in LIMITED_ACCESS_CATEGORIES


def _multiplier_for_stop(stop_type: str, tariff: LimitedAccessTariff) -> Decimal:
    if stop_type == "pickup":
        return tariff.pickup_multiplier
    return tariff.delivery_multiplier


def _apply_cap(amount: Decimal, cap: Decimal | None) -> Decimal:
    if cap is not None and amount > cap:
        return cap
    return amount


def calculate_limited_access_fee(
    stop: StopFacts, tariff: LimitedAccessTariff = LimitedAccessTariff()
) -> Decimal:
    """Return the limited-access surcharge for one stop in dollars.

    A qualifying stop bills at the tariff base fee for deliveries or the reduced
    pickup multiplier for pickups. Matching multiple limited-access tags still
    bills only one charge per stop. Remote-area add-on applies only when the stop
    otherwise qualifies. Final amount is rounded half up to cents and capped.
    """
    _validate(stop, tariff)

    if stop.already_applied:
        return Decimal("0.00")
    if stop.matched_tags == 0:
        return Decimal("0.00")
    if not _is_limited_access_category(stop.category):
        return Decimal("0.00")

    base = tariff.base_fee * _multiplier_for_stop(stop.stop_type, tariff)
    amount = base
    if stop.remote_area:
        amount += tariff.remote_add_on

    rounded = amount.quantize(CENT, rounding=ROUND_HALF_UP)
    return _apply_cap(rounded, tariff.fee_cap)
