from edi_l11_reference_priority import (
    L11Reference,
    ReferenceContext,
    prioritize_edi_l11_references,
)


def test_default_ranking_prefers_pro_then_bol_then_po():
    refs = [
        L11Reference("PO", "AB1234"),
        L11Reference("BOL", "76543210"),
        L11Reference("PRO", "123456789"),
    ]
    result = prioritize_edi_l11_references(refs, ReferenceContext(customer_code="GEN"))
    assert result == [
        L11Reference("PRO", "123456789"),
        L11Reference("BOL", "76543210"),
        L11Reference("PO", "AB1234"),
    ]


def test_blank_and_short_values_are_ignored_except_sid():
    refs = [
        L11Reference("PO", "   "),
        L11Reference("WO", "A1"),
        L11Reference("SID", "A1"),
    ]
    result = prioritize_edi_l11_references(refs, ReferenceContext(customer_code="GEN"))
    assert result == [L11Reference("SID", "A1")]


def test_non_pro_numeric_value_over_12_digits_is_ignored():
    refs = [
        L11Reference("BOL", "1234567890123"),
        L11Reference("PO", "PO7788"),
    ]
    result = prioritize_edi_l11_references(refs, ReferenceContext(customer_code="GEN"))
    assert result == [L11Reference("PO", "PO7788")]


def test_pro_allows_up_to_14_digits_but_not_more():
    refs = [
        L11Reference("PRO", "12345678901234"),
        L11Reference("PRO", "123456789012345"),
        L11Reference("BOL", "BOL55"),
    ]
    result = prioritize_edi_l11_references(refs, ReferenceContext(customer_code="GEN"))
    assert result == [
        L11Reference("PRO", "12345678901234"),
        L11Reference("BOL", "BOL55"),
    ]


def test_acme_prefers_qualifying_po_over_pro():
    refs = [
        L11Reference("PRO", "1234567"),
        L11Reference("PO", "ZX-9012"),
    ]
    result = prioritize_edi_l11_references(refs, ReferenceContext(customer_code="ACME"))
    assert result == [
        L11Reference("PO", "ZX-9012"),
        L11Reference("PRO", "1234567"),
    ]


def test_hart_suppresses_tmp_po_and_prefers_exact_8_digit_bol_over_pro():
    refs = [
        L11Reference("PO", "TMP-4455"),
        L11Reference("PRO", "123456789"),
        L11Reference("BOL", "87654321"),
    ]
    result = prioritize_edi_l11_references(refs, ReferenceContext(customer_code="HART"))
    assert result == [
        L11Reference("BOL", "87654321"),
        L11Reference("PRO", "123456789"),
    ]


def test_duplicate_normalized_values_keep_best_qualifier_and_trim_spaces():
    refs = [
        L11Reference("PO", "  ABC   123  "),
        L11Reference("BOL", "ABC 123"),
        L11Reference("WO", "ZZ999"),
    ]
    result = prioritize_edi_l11_references(refs, ReferenceContext(customer_code="GEN"))
    assert result == [
        L11Reference("BOL", "ABC 123"),
        L11Reference("WO", "ZZ999"),
    ]


def test_ltl_boost_keeps_pro_first():
    refs = [
        L11Reference("BOL", "44556677"),
        L11Reference("PRO", "99887766"),
    ]
    result = prioritize_edi_l11_references(
        refs, ReferenceContext(customer_code="GEN", shipment_mode="LTL")
    )
    assert result == [
        L11Reference("PRO", "99887766"),
        L11Reference("BOL", "44556677"),
    ]


def test_stop_count_boost_can_raise_sid_above_unknown_and_limit_to_three_results():
    refs = [
        L11Reference("ZZ", "MISC777"),
        L11Reference("SID", "S12"),
        L11Reference("WO", "WORK900"),
        L11Reference("OQ", "OQ555"),
    ]
    result = prioritize_edi_l11_references(
        refs, ReferenceContext(customer_code="GEN", stop_count=5)
    )
    assert result == [
        L11Reference("WO", "WORK900"),
        L11Reference("SID", "S12"),
        L11Reference("OQ", "OQ555"),
    ]
