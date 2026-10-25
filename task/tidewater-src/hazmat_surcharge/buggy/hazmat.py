"""Hazmat handling on truckload and LTL loads.

Two separate questions are answered here. ``requires_placards`` says whether the
truck must display hazmat placards, which dispatch uses to pick a driver with the
hazmat endorsement: a load needs placards at 1,001 lb or more aggregate hazmat
weight, or for any amount of a Table 1 material. ``hazmat_surcharge`` is what the
customer pays for hazmat on the load, which settlement adds as an accessorial.
"""

from dataclasses import dataclass
from decimal import Decimal

HAZMAT_SURCHARGE = Decimal("150.00")
PLACARD_THRESHOLD_LB = Decimal("1001")
# Hazard classes placarded at any quantity (49 CFR 172.504 Table 1, simplified).
TABLE_1_CLASSES = frozenset({"1.1", "1.2", "1.3", "2.3", "4.3", "6.1-PIH", "7"})


@dataclass(frozen=True)
class FreightLine:
    description: str
    weight_lb: Decimal
    un_number: str | None = None
    hazard_class: str | None = None

    @property
    def is_hazmat(self) -> bool:
        return self.un_number is not None


@dataclass(frozen=True)
class Load:
    load_id: str
    customer: str
    lines: tuple[FreightLine, ...]


def hazmat_weight(load: Load) -> Decimal:
    return sum((line.weight_lb for line in load.lines if line.is_hazmat), Decimal("0"))


def requires_placards(load: Load) -> bool:
    if any(line.is_hazmat and line.hazard_class in TABLE_1_CLASSES for line in load.lines):
        return True
    return hazmat_weight(load) >= PLACARD_THRESHOLD_LB


def hazmat_surcharge(load: Load) -> Decimal:
    """The hazmat accessorial: a flat charge for any hazmat on the load."""
    if any(line.is_hazmat for line in load.lines):
        return HAZMAT_SURCHARGE
    return Decimal("0.00")
