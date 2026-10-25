from decimal import Decimal

import pytest

from edi_n1_role_resolver import N1Party, RoleContext, ResolvedRoles, resolve_edi_n1_roles


def test_204_precedence_prefers_sf_st_and_bt():
    parties = [
        N1Party("SH", "Legacy Shipper", 5),
        N1Party("SF", "Actual Shipper", 10),
        N1Party("CN", "Legacy Consignee", 15),
        N1Party("ST", "Actual Consignee", 20),
        N1Party("BY", "Buyer Billing", 25),
        N1Party("BT", "Bill To", 30),
    ]
    assert resolve_edi_n1_roles(parties, RoleContext("204")) == ResolvedRoles(
        shipper="Actual Shipper",
        consignee="Actual Consignee",
        bill_to="Bill To",
        payer="Bill To",
    )


def test_210_billing_prefers_bt_over_re():
    parties = [
        N1Party("RE", "Remit Party", 10),
        N1Party("BT", "Invoice Party", 20),
    ]
    result = resolve_edi_n1_roles(parties, RoleContext("210"))
    assert result.bill_to == "Invoice Party"
    assert result.payer == "Invoice Party"


def test_214_z7_can_set_shipper_for_first_pickup_event():
    parties = [N1Party("Z7", "Origin Facility", 10)]
    result = resolve_edi_n1_roles(parties, RoleContext("214", event_code="X3", stop_sequence=1))
    assert result.shipper == "Origin Facility"


def test_214_z7_does_not_set_shipper_for_later_stop():
    parties = [N1Party("Z7", "Origin Facility", 10)]
    result = resolve_edi_n1_roles(parties, RoleContext("214", event_code="X3", stop_sequence=2))
    assert result.shipper is None


def test_low_confidence_payer_is_ignored_and_falls_back_to_bill_to():
    parties = [
        N1Party("BT", "Accounts Payable", 10),
        N1Party("PR", "Weak Payer", 20, confidence=Decimal("0.4994")),
    ]
    result = resolve_edi_n1_roles(parties, RoleContext("204"))
    assert result.bill_to == "Accounts Payable"
    assert result.payer == "Accounts Payable"


def test_confidence_rounding_allows_threshold_match():
    parties = [
        N1Party("BT", "Accounts Payable", 10),
        N1Party("PR", "Rounded Payer", 20, confidence=Decimal("0.4995")),
    ]
    result = resolve_edi_n1_roles(parties, RoleContext("204"))
    assert result.payer == "Rounded Payer"


def test_duplicate_qualifier_uses_earliest_loop_position():
    parties = [
        N1Party("ST", "First Consignee", 30),
        N1Party("st", "Later Consignee", 40),
    ]
    result = resolve_edi_n1_roles(parties, RoleContext("204"))
    assert result.consignee == "First Consignee"


def test_qualifiers_are_trimmed_and_case_insensitive():
    parties = [
        N1Party(" sf ", "Shipper", 10),
        N1Party(" st", "Consignee", 20),
        N1Party(" bt ", "Biller", 30),
    ]
    assert resolve_edi_n1_roles(parties, RoleContext("204")) == ResolvedRoles(
        shipper="Shipper",
        consignee="Consignee",
        bill_to="Biller",
        payer="Biller",
    )


def test_unsupported_transaction_type_is_rejected():
    with pytest.raises(ValueError):
        resolve_edi_n1_roles([N1Party("SF", "X", 1)], RoleContext("990"))


def test_stop_sequence_must_be_positive_when_provided():
    with pytest.raises(ValueError):
        resolve_edi_n1_roles([N1Party("Z7", "X", 1)], RoleContext("214", event_code="X1", stop_sequence=0))
