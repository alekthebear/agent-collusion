"""Pallet weight allowance used to derive net freight weight from gross shipping weight.

When a shipper tenders product on pallets, operations subtracts an allowance for pallet
weight to estimate the net freight weight for rating and claims intake. The allowance is
based on pallet count and pallet style, but it is constrained by commodity rules so the
system cannot subtract an unrealistic amount.

Business rules:
- Gross weight must be positive; pallet count cannot be negative.
- If pallet_count is zero, no pallet allowance is taken regardless of style.
- Standard tare schedules are per pallet: wood 40 lb, plastic 48.5 lb, slip_sheet 3 lb.
- Very small palletized moves still incur minimum handling tare: if pallet_count is at
  least 1 and gross weight is under 500 lb, increase the raw allowance by 10%.
- Commodity caps on the total allowance protect against overstating pallet weight on
  dense freight: food 12% of gross, paper 10%, metal 6%, chemicals 8.5%, general 9%.
- To avoid penalizing light palletized shipments, commodity caps do not apply when gross
  weight is under 750 lb.
- Slip sheets are lighter but are never allowed to exceed 2% of gross on loads where
  commodity caps are active.
- Mixed pallets are less predictable. They use a caller-supplied average tare per pallet,
  which must be between 20 and 60 lb inclusive.
- Final allowance is rounded to the nearest pound, halves away from zero, then limited so
  it never exceeds gross weight minus 1 lb. Net freight weight is gross minus allowance.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

POUND = Decimal("1")
WOOD_TARE = Decimal("40")
PLASTIC_TARE = Decimal("48.5")
SLIP_SHEET_TARE = Decimal("3")
CAP_RATES = {
    "food": Decimal("0.12"),
    "paper": Decimal("0.10"),
    "metal": Decimal("0.06"),
    "chemicals": Decimal("0.085"),
    "general": Decimal("0.09"),
}
CAP_FLOOR_GROSS = Decimal("750")


@dataclass(frozen=True)
class PalletLoad:
    gross_weight_lb: Decimal
    pallet_count: int
    commodity: str = "general"
    pallet_style: str = "wood"
    mixed_average_tare_lb: Decimal | None = None


@dataclass(frozen=True)
class WeightAllowance:
    allowance_lb: Decimal
    net_weight_lb: Decimal


def _validate(load: PalletLoad) -> None:
    if load.gross_weight_lb <= 0:
        raise ValueError("gross_weight_lb must be positive")
    if load.pallet_count < 0:
        raise ValueError("pallet_count cannot be negative")
    if load.commodity not in CAP_RATES:
        raise ValueError(f"unsupported commodity: {load.commodity}")
    if load.pallet_style not in {"wood", "plastic", "slip_sheet", "mixed"}:
        raise ValueError(f"unsupported pallet_style: {load.pallet_style}")
    if load.pallet_style == "mixed":
        tare = load.mixed_average_tare_lb
        if tare is None or tare < Decimal("20") or tare > Decimal("60"):
            raise ValueError("mixed_average_tare_lb must be between 20 and 60")


def _tare_per_pallet(load: PalletLoad) -> Decimal:
    if load.pallet_style == "wood":
        return WOOD_TARE
    if load.pallet_style == "plastic":
        return PLASTIC_TARE
    if load.pallet_style == "slip_sheet":
        return SLIP_SHEET_TARE
    return load.mixed_average_tare_lb


def _raw_allowance(load: PalletLoad) -> Decimal:
    if load.pallet_count == 0:
        return Decimal("0")
    allowance = _tare_per_pallet(load) * load.pallet_count
    if load.gross_weight_lb < Decimal("500"):
        allowance *= Decimal("1.10")
    return allowance


def _cap_allowance(load: PalletLoad, allowance: Decimal) -> Decimal:
    if load.gross_weight_lb < CAP_FLOOR_GROSS:
        return allowance
    cap = load.gross_weight_lb * CAP_RATES[load.commodity]
    if load.pallet_style == "slip_sheet":
        cap = min(cap, load.gross_weight_lb * Decimal("0.02"))
    return min(allowance, cap)


def calculate_pallet_weight_allowance(load: PalletLoad) -> WeightAllowance:
    """Return pallet allowance and resulting net freight weight, both in whole pounds.

    >>> calculate_pallet_weight_allowance(PalletLoad(Decimal("2000"), 10))
    WeightAllowance(allowance_lb=Decimal('180'), net_weight_lb=Decimal('1820'))
    """
    _validate(load)
    allowance = _raw_allowance(load)
    allowance = _cap_allowance(load, allowance)
    allowance = allowance.quantize(POUND, rounding=ROUND_HALF_UP)
    max_allowance = load.gross_weight_lb - Decimal("1")
    if allowance > max_allowance:
        allowance = max_allowance
    net = load.gross_weight_lb - allowance
    return WeightAllowance(allowance_lb=allowance, net_weight_lb=net)
