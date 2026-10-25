from datetime import date
from decimal import Decimal

from edi_204_stop_normalizer import EDI204Stop, normalize_edi_204_stops


def test_duplicate_stops_merge_on_cleaned_location_and_date():
    stops = [
        EDI204Stop("P", 20, " Dallas ", "tx", "75201-1234", date(2026, 4, 2), Decimal("100.4")),
        EDI204Stop("CL", 25, "DALLAS", "TX", "75201", date(2026, 4, 2), Decimal("49.5")),
    ]
    result = normalize_edi_204_stops(stops)
    assert len(result) == 1
    assert result[0].city == "DALLAS"
    assert result[0].postal_code == "75201"
    assert result[0].source_count == 2
    assert result[0].weight_lb == Decimal("150")


def test_delivery_role_outranks_pickup_for_single_code_precedence_but_mixed_when_both_present():
    stops = [
        EDI204Stop("P", 10, "Tulsa", "OK", "74103", date(2026, 5, 1), Decimal("10")),
        EDI204Stop("D", 12, "Tulsa", "OK", "74103", date(2026, 5, 1), Decimal("15")),
    ]
    result = normalize_edi_204_stops(stops)
    assert result[0].role == "mixed"


def test_stopoff_overrides_mixed_role():
    stops = [
        EDI204Stop("P", 10, "Omaha", "NE", "68102", date(2026, 6, 1), Decimal("5")),
        EDI204Stop("UL", 11, "Omaha", "NE", "68102", date(2026, 6, 1), Decimal("5")),
        EDI204Stop("SO", 9, "Omaha", "NE", "68102", date(2026, 6, 1), Decimal("5")),
    ]
    result = normalize_edi_204_stops(stops)
    assert result[0].role == "stopoff"


def test_missing_and_nonpositive_sequences_sort_after_positive_sequences():
    stops = [
        EDI204Stop("P", None, "Late", "MO", "64000", date(2026, 7, 3), Decimal("1")),
        EDI204Stop("P", 0, "Also Late", "MO", "64001", date(2026, 7, 2), Decimal("1")),
        EDI204Stop("P", 5, "First", "MO", "64002", date(2026, 7, 4), Decimal("1")),
    ]
    result = normalize_edi_204_stops(stops)
    assert [r.city for r in result] == ["FIRST", "ALSO LATE", "LATE"]
    assert [r.standardized_sequence for r in result] == [10, 20, 30]


def test_lowest_positive_sequence_within_duplicate_group_is_used():
    stops = [
        EDI204Stop("P", 30, "Wichita", "KS", "67202", date(2026, 8, 1), Decimal("20")),
        EDI204Stop("CL", 8, "Wichita", "KS", "67202", date(2026, 8, 1), Decimal("20")),
        EDI204Stop("D", 15, "Topeka", "KS", "66603", date(2026, 8, 1), Decimal("20")),
    ]
    result = normalize_edi_204_stops(stops)
    assert [r.city for r in result] == ["WICHITA", "TOPEKA"]


def test_blank_appointment_only_matches_blank_appointment():
    stops = [
        EDI204Stop("P", 1, "Denver", "CO", "80202", None, Decimal("10")),
        EDI204Stop("P", 2, "Denver", "CO", "80202", date(2026, 9, 1), Decimal("10")),
    ]
    result = normalize_edi_204_stops(stops)
    assert len(result) == 2


def test_negative_weight_is_treated_as_zero():
    stops = [
        EDI204Stop("P", 1, "Amarillo", "TX", "79101", date(2026, 10, 1), Decimal("-25.7")),
        EDI204Stop("P", 1, "Amarillo", "TX", "79101", date(2026, 10, 1), Decimal("10.2")),
    ]
    result = normalize_edi_204_stops(stops)
    assert result[0].weight_lb == Decimal("10")


def test_weight_rounds_half_up_to_whole_pounds():
    stops = [
        EDI204Stop("D", 1, "Peoria", "IL", "61602", date(2026, 11, 1), Decimal("100.5")),
    ]
    result = normalize_edi_204_stops(stops)
    assert result[0].weight_lb == Decimal("101")


def test_weight_is_capped_at_maximum_group_total():
    stops = [
        EDI204Stop("D", 1, "Memphis", "TN", "38103", date(2026, 12, 1), Decimal("80000.6")),
        EDI204Stop("D", 1, "Memphis", "TN", "38103", date(2026, 12, 1), Decimal("25000.6")),
    ]
    result = normalize_edi_204_stops(stops)
    assert result[0].weight_lb == Decimal("99999")
