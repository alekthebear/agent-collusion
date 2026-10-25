"""Residential delivery charges for shipments tendered to homes and similar non-commercial sites.

The billing service calls ``calculate_residential_delivery_fee`` once per shipment when
rating an accessorial. Standard Tidewater rules are:

* No residential fee applies when the destination is commercial.
* Parcel moves use weight breaks with a surcharge for oversized pieces.
* LTL moves use pallet and weight thresholds; very small dock-friendly drops get a
  reduced minimum fee.
* Remote residential destinations add a fixed tariff on top of the base fee.
* Contract customers may waive the fee entirely, receive a percent discount, or be
  subject to a per-shipment cap. Discounts apply before the cap.
* Charges are rounded half up to the cent, and oversized or remote surcharges are not
  assessed when the residential fee is fully waived.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
PARCEL_BASE_UNDER_70 = Decimal("4.50")
PARCEL_BASE_70_TO_150 = Decimal("8.00")
PARCEL_OVERSIZE_SURCHARGE = Decimal("12.50")
LTL_MINIMUM_FEE = Decimal("32.00")
LTL_SMALL_DROP_FEE = Decimal("18.00")
LTL_HEAVY_FEE = Decimal("48.00")
LTL_EXTRA_HEAVY_FEE = Decimal("72.00")
REMOTE_SURCHARGE = Decimal("9.75")


@dataclass(frozen=True)
class ShipmentFacts:
    destination_type: str
    mode: str
    billed_weight_lb: Decimal
    pieces: int = 1
    pallets: int = 0
    longest_side_in: int = 0
    remote_zip: bool = False
    liftgate_requested: bool = False


@dataclass(frozen=True)
class ResidentialTariff:
    residential_waived: bool = False
    discount_percent: Decimal = Decimal("0")
    shipment_cap: Decimal | None = None


def _validate(shipment: ShipmentFacts, tariff: ResidentialTariff) -> None:
    if shipment.destination_type not in {"residential", "commercial"}:
        raise ValueError("destination_type must be 'residential' or 'commercial'")
    if shipment.mode not in {"parcel", "ltl"}:
        raise ValueError("mode must be 'parcel' or 'ltl'")
    if shipment.billed_weight_lb < 0:
        raise ValueError("billed_weight_lb cannot be negative")
    if shipment.pieces < 1:
        raise ValueError("pieces must be at least 1")
    if shipment.pallets < 0:
        raise ValueError("pallets cannot be negative")
    if not (Decimal("0") <= tariff.discount_percent <= Decimal("100")):
        raise ValueError("discount_percent must be between 0 and 100")
    if tariff.shipment_cap is not None and tariff.shipment_cap < 0:
        raise ValueError("shipment_cap cannot be negative")


def _parcel_fee(shipment: ShipmentFacts) -> Decimal:
    if shipment.billed_weight_lb <= Decimal("70"):
        base = PARCEL_BASE_UNDER_70
    else:
        base = PARCEL_BASE_70_TO_150
    if shipment.longest_side_in > 48 or shipment.billed_weight_lb > Decimal("120"):
        base += PARCEL_OVERSIZE_SURCHARGE
    return base


def _ltl_fee(shipment: ShipmentFacts) -> Decimal:
    if (
        shipment.billed_weight_lb <= Decimal("150")
        and shipment.pallets == 0
        and not shipment.liftgate_requested
    ):
        return LTL_SMALL_DROP_FEE
    if shipment.billed_weight_lb > Decimal("1200") or shipment.pallets >= 4:
        return LTL_EXTRA_HEAVY_FEE
    if shipment.billed_weight_lb > Decimal("500") or shipment.pallets >= 2:
        return LTL_HEAVY_FEE
    return LTL_MINIMUM_FEE


def _apply_discount(amount: Decimal, discount_percent: Decimal) -> Decimal:
    if discount_percent == 0:
        return amount
    multiplier = (Decimal("100") - discount_percent) / Decimal("100")
    return amount * multiplier


def _apply_cap(amount: Decimal, cap: Decimal | None) -> Decimal:
    if cap is not None and amount > cap:
        return cap
    return amount


def calculate_residential_delivery_fee(
    shipment: ShipmentFacts, tariff: ResidentialTariff = ResidentialTariff()
) -> Decimal:
    """Residential delivery fee owed for one shipment.

    Residential fees apply only to residential destinations. Parcel thresholds are at
    70 lb and 120 lb, with an oversize trigger above 48 inches on the longest side.
    LTL thresholds are small-drop, heavy, and extra-heavy breaks. A remote zip code
    adds a fixed surcharge after the mode-based fee is determined. Contract discounts
    then apply, followed by any cap.
    """
    _validate(shipment, tariff)
    if shipment.destination_type == "commercial" or tariff.residential_waived:
        return Decimal("0.00")
    amount = _parcel_fee(shipment) if shipment.mode == "parcel" else _ltl_fee(shipment)
    if shipment.remote_zip:
        amount += REMOTE_SURCHARGE
    amount = _apply_discount(amount, tariff.discount_percent)
    amount = _apply_cap(amount, tariff.shipment_cap)
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)
