"""Net salvage recovery on cargo claims after disposal and insurer participation.

Tidewater settles cargo shortages and damaged-freight claims at the load line item or
whole-load level. When damaged freight has resale or scrap value, that salvage reduces
our net exposure, but only to the extent the recovery is real and collectible.

Business rules:
- ``gross_claim`` is the starting customer claim before salvage.
- ``salvage_percent`` estimates what share of the gross claim is recoverable through
  resale, expressed from 0 to 100 inclusive.
- ``recovery_value`` is a known market bid or resale amount. We credit the larger of
  the estimated salvage amount and the known recovery value.
- ``disposal_cost`` reduces salvage dollars because handling, dump, and rework costs
  come out of the proceeds.
- Negative net salvage is treated as zero; salvage cannot increase exposure.
- If ``hazmat`` is true, only 80% of net salvage is collectible because of regulated
  handling leakage.
- If net salvage is under $25.00, it is ignored as immaterial.
- If ``insurer_participates`` is true, the insurer takes 70% of salvage above the
  deductible. Below or at the deductible, salvage offsets only Tidewater's retained
  exposure.
- Exposure can never go below zero and is rounded to the nearest cent using half-up.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
MIN_SALVAGE_CREDIT = Decimal("25.00")
HAZMAT_COLLECTIBLE_FACTOR = Decimal("0.80")
INSURER_SHARE = Decimal("0.70")


@dataclass(frozen=True)
class SalvageInputs:
    gross_claim: Decimal
    salvage_percent: Decimal
    recovery_value: Decimal = Decimal("0.00")
    disposal_cost: Decimal = Decimal("0.00")
    deductible: Decimal = Decimal("500.00")
    insurer_participates: bool = True
    hazmat: bool = False


@dataclass(frozen=True)
class SalvageBreakdown:
    estimated_salvage: Decimal
    gross_salvage_credit: Decimal
    net_salvage_credit: Decimal
    tidewater_salvage_credit: Decimal
    insurer_salvage_credit: Decimal
    net_exposure: Decimal


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _validate(claim: SalvageInputs) -> None:
    if claim.gross_claim < 0:
        raise ValueError("gross_claim must be non-negative")
    if claim.recovery_value < 0:
        raise ValueError("recovery_value must be non-negative")
    if claim.disposal_cost < 0:
        raise ValueError("disposal_cost must be non-negative")
    if claim.deductible < 0:
        raise ValueError("deductible must be non-negative")
    if not (Decimal("0") <= claim.salvage_percent <= Decimal("100")):
        raise ValueError("salvage_percent must be between 0 and 100")


def _gross_salvage_credit(claim: SalvageInputs) -> Decimal:
    estimated = claim.gross_claim * claim.salvage_percent / Decimal("100")
    return max(estimated, claim.recovery_value)


def _net_salvage_credit(claim: SalvageInputs) -> Decimal:
    credit = _gross_salvage_credit(claim) - claim.disposal_cost
    if credit <= 0:
        return Decimal("0.00")
    if claim.hazmat:
        credit *= HAZMAT_COLLECTIBLE_FACTOR
    credit = _money(credit)
    if credit < MIN_SALVAGE_CREDIT:
        return Decimal("0.00")
    if credit > claim.gross_claim:
        return claim.gross_claim
    return credit


def _allocate_salvage(claim: SalvageInputs, net_credit: Decimal) -> tuple[Decimal, Decimal]:
    if net_credit == 0:
        return Decimal("0.00"), Decimal("0.00")
    if not claim.insurer_participates:
        return net_credit, Decimal("0.00")
    if claim.gross_claim <= claim.deductible:
        return net_credit, Decimal("0.00")
    excess_credit = max(net_credit - claim.deductible, Decimal("0.00"))
    insurer_credit = _money(excess_credit * INSURER_SHARE)
    if insurer_credit > net_credit:
        insurer_credit = net_credit
    tidewater_credit = net_credit - insurer_credit
    return tidewater_credit, insurer_credit


def calculate_salvage_recovery(claim: SalvageInputs) -> SalvageBreakdown:
    """Compute net claim exposure after salvage and insurer participation.

    The credited salvage is the larger of percentage-based estimate and known recovery,
    less disposal cost, subject to hazmat collectibility, immaterial minimums, and a
    ceiling at the gross claim amount. Any insurer participation affects reporting of
    who benefits from salvage, but total exposure is always reduced by the full net
    salvage credit.
    """
    _validate(claim)
    estimated = _money(claim.gross_claim * claim.salvage_percent / Decimal("100"))
    gross_credit = _money(_gross_salvage_credit(claim))
    net_credit = _net_salvage_credit(claim)
    tidewater_credit, insurer_credit = _allocate_salvage(claim, net_credit)
    exposure = _money(claim.gross_claim - net_credit)
    if exposure < 0:
        exposure = Decimal("0.00")
    return SalvageBreakdown(
        estimated_salvage=estimated,
        gross_salvage_credit=gross_credit,
        net_salvage_credit=net_credit,
        tidewater_salvage_credit=_money(tidewater_credit),
        insurer_salvage_credit=_money(insurer_credit),
        net_exposure=exposure,
    )
