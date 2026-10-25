from bol_reference_parser import ParsedReference, RawReferenceSet, parse_bol_references


def test_prefixed_bol_token_normalizes_punctuation_and_zeroes():
    raw = RawReferenceSet(references=("bol-00012345",))
    assert parse_bol_references(raw) == (ParsedReference("BOL", "12345"),)


def test_label_then_value_uses_pending_prefix():
    raw = RawReferenceSet(references=("PO", "0019"))
    assert parse_bol_references(raw) == (ParsedReference("PO", "19"),)


def test_bare_numeric_token_in_bol_length_window_becomes_bol():
    raw = RawReferenceSet(references=("  00123456  ",))
    assert parse_bol_references(raw) == (ParsedReference("BOL", "123456"),)


def test_short_values_follow_prefix_specific_minimums():
    raw = RawReferenceSet(references=("PO-09", "BOL-09", "PU-0"))
    assert parse_bol_references(raw) == (
        ParsedReference("PO", "9"),
        ParsedReference("PU", "0"),
    )


def test_long_numeric_payload_keeps_last_twelve_digits():
    raw = RawReferenceSet(references=("SO123456789012345",))
    assert parse_bol_references(raw) == (ParsedReference("SO", "456789012345"),)


def test_long_alphanumeric_payload_is_rejected():
    raw = RawReferenceSet(references=("PO-ABC1234567890",))
    assert parse_bol_references(raw) == ()


def test_duplicate_references_are_suppressed_after_normalization():
    raw = RawReferenceSet(references=("BOL-000123", "123", "BILL 000123", "BOL000123"))
    assert parse_bol_references(raw) == (ParsedReference("BOL", "123"),)


def test_label_without_following_value_produces_nothing():
    raw = RawReferenceSet(references=("pickup",))
    assert parse_bol_references(raw) == ()


def test_order_is_preserved_across_multiple_reference_types():
    raw = RawReferenceSet(references=("PO-22", "SO 000777", "987654"))
    assert parse_bol_references(raw) == (
        ParsedReference("PO", "22"),
        ParsedReference("SO", "777"),
        ParsedReference("BOL", "987654"),
    )
