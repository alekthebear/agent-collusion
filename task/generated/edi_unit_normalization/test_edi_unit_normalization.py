from decimal import Decimal

import pytest

from edi_unit_normalization import EDIQuantity, NormalizedUnits, normalize_edi_units


def test_kilograms_convert_to_pounds_with_cent_rounding():
    item = EDIQuantity(quantity=Decimal("10"), unit_code="KG", transaction_set="204")
    assert normalize_edi_units(item) == NormalizedUnits(Decimal("22.05"), "LB")


def test_small_positive_weight_rounds_up_to_one_pound():
    item = EDIQuantity(quantity=Decimal("0.20"), unit_code="KG", transaction_set="204")
    assert normalize_edi_units(item) == NormalizedUnits(Decimal("1"), "LB")


def test_weight_above_maximum_is_rejected():
    item = EDIQuantity(quantity=Decimal("48000.01"), unit_code="LB", transaction_set="204")
    with pytest.raises(ValueError):
        normalize_edi_units(item)


def test_feet_convert_to_whole_inches():
    item = EDIQuantity(quantity=Decimal("2.5"), unit_code="FT", transaction_set="204")
    assert normalize_edi_units(item) == NormalizedUnits(Decimal("30"), "IN")


def test_sub_inch_dimension_rounds_up_to_one_inch():
    item = EDIQuantity(quantity=Decimal("0.5"), unit_code="CM", transaction_set="204")
    assert normalize_edi_units(item) == NormalizedUnits(Decimal("1"), "IN")


def test_dimension_boundary_at_maximum_is_allowed():
    item = EDIQuantity(quantity=Decimal("1080"), unit_code="IN", transaction_set="204")
    assert normalize_edi_units(item) == NormalizedUnits(Decimal("1080"), "IN")


def test_invoice_pc_is_treated_as_pieces():
    item = EDIQuantity(quantity=Decimal("2.5"), unit_code="PC", transaction_set="210")
    assert normalize_edi_units(item) == NormalizedUnits(Decimal("3"), "EA")


def test_positive_fractional_count_rounds_half_up():
    item = EDIQuantity(quantity=Decimal("1.5"), unit_code="CT", transaction_set="204")
    assert normalize_edi_units(item) == NormalizedUnits(Decimal("2"), "EA")


def test_214_m_code_is_rejected_as_minutes_override():
    item = EDIQuantity(quantity=Decimal("7"), unit_code="M", transaction_set="214")
    with pytest.raises(ValueError):
        normalize_edi_units(item)


def test_negative_quantity_is_rejected():
    item = EDIQuantity(quantity=Decimal("-1"), unit_code="EA", transaction_set="204")
    with pytest.raises(ValueError):
        normalize_edi_units(item)
