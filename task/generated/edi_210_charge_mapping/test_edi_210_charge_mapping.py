from decimal import Decimal

import pytest

from edi_210_charge_mapping import EDI210ChargeLine, MappedCharge, map_edi_210_charges


def test_negative_amount_is_credit_regardless_of_code():
    line = EDI210ChargeLine(amount=Decimal("-12.345"), code="405", description="Fuel surcharge")
    assert map_edi_210_charges(line) == MappedCharge("credit", Decimal("-12.35"), "amount")


def test_zero_amount_is_ignored():
    line = EDI210ChargeLine(amount=Decimal("0"), code="DET", description="Detention")
    assert map_edi_210_charges(line) == MappedCharge("ignore", Decimal("0.00"), "amount")


def test_linehaul_code_with_fuel_description_maps_to_fuel():
    line = EDI210ChargeLine(amount=Decimal("150.00"), code="400", description="Fuel Surcharge")
    assert map_edi_210_charges(line) == MappedCharge("fuel", Decimal("150.00"), "description")


def test_known_code_maps_directly_when_no_override_applies():
    line = EDI210ChargeLine(amount=Decimal("85.00"), code="DLY", description="service fee")
    assert map_edi_210_charges(line) == MappedCharge("detention", Decimal("85.00"), "code")


def test_description_overrides_generic_code_for_lumper():
    line = EDI210ChargeLine(amount=Decimal("175.00"), code="999", description="Lumper unloading crew")
    assert map_edi_210_charges(line) == MappedCharge("lumper", Decimal("175.00"), "description")


def test_explicit_code_beats_non_priority_description_conflict():
    line = EDI210ChargeLine(amount=Decimal("40.00"), code="STP", description="line haul adjustment")
    assert map_edi_210_charges(line) == MappedCharge("stopoff", Decimal("40.00"), "code")


def test_small_uncoded_positive_amount_defaults_to_misc():
    line = EDI210ChargeLine(amount=Decimal("24.994"), code=None, description="paperwork")
    assert map_edi_210_charges(line) == MappedCharge("misc", Decimal("24.99"), "fallback")


def test_threshold_amount_at_25_defaults_to_other():
    line = EDI210ChargeLine(amount=Decimal("25.00"), code="", description="paperwork")
    assert map_edi_210_charges(line) == MappedCharge("other", Decimal("25.00"), "fallback")


def test_unknown_nonblank_code_without_description_defaults_to_other():
    line = EDI210ChargeLine(amount=Decimal("10.00"), code="ABC", description="")
    assert map_edi_210_charges(line) == MappedCharge("other", Decimal("10.00"), "fallback")


def test_code_is_trimmed_and_uppercased_before_mapping():
    line = EDI210ChargeLine(amount=Decimal("33.33"), code="  fsc ", description="")
    assert map_edi_210_charges(line) == MappedCharge("fuel", Decimal("33.33"), "code")
