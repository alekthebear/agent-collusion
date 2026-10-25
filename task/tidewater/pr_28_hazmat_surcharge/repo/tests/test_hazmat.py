from decimal import Decimal

from hazmat import FreightLine, Load, hazmat_surcharge, requires_placards

GROCERY = FreightLine("dry grocery", Decimal("37660"))
AEROSOL = FreightLine("aerosol cleaner", Decimal("340"), "UN1950", "2.1")


def load(*lines):
    return Load("TW-92210", "HARTLINE", lines)


def test_load_without_hazmat_has_no_surcharge():
    assert hazmat_surcharge(load(GROCERY)) == Decimal("0.00")
    assert not requires_placards(load(GROCERY))


def test_placards_needed_at_1001_lb():
    heavy = FreightLine("aerosol cleaner", Decimal("1001"), "UN1950", "2.1")
    assert requires_placards(load(GROCERY, heavy))


def test_table_1_material_is_placarded_at_any_weight():
    pih = FreightLine("chlorine cylinders", Decimal("90"), "UN1017", "2.3")
    assert requires_placards(load(pih))


def test_small_hazmat_quantity_is_not_placarded():
    assert not requires_placards(load(GROCERY, AEROSOL))


def test_unplacarded_hazmat_still_pays_the_surcharge():
    # The surcharge applies to any hazmat on the load, placarded or not: carrier
    # contract §9.1. It pays for the shipping-paper review, the 24-hour emergency
    # response service, and the cargo insurance rider, all of which apply to every
    # hazmat load whatever its weight.
    assert hazmat_surcharge(load(GROCERY, AEROSOL)) == Decimal("150.00")


def test_surcharge_is_flat_per_load():
    second = FreightLine("lamp oil", Decimal("120"), "UN1223", "3")
    assert hazmat_surcharge(load(GROCERY, AEROSOL, second)) == Decimal("150.00")
