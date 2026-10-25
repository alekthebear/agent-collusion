from datetime import date, datetime, time

import pytest

from edi_date_qualifier_resolver import EdiQualifierValue, resolve_edi_date_qualifiers


def test_higher_precedence_pickup_beats_lower_even_if_later():
    values = [
        EdiQualifierValue("AF", date(2026, 6, 1), time(7, 0), -300),
        EdiQualifierValue("X3", date(2026, 6, 1), time(9, 0), -300),
    ]
    result = resolve_edi_date_qualifiers(values)
    assert result.pickup_at == datetime(2026, 6, 1, 14, 0)


def test_earliest_value_within_same_precedence_group_wins():
    values = [
        EdiQualifierValue("X3", date(2026, 6, 1), time(10, 0), -300),
        EdiQualifierValue("X3", date(2026, 6, 1), time(8, 30), -300),
    ]
    result = resolve_edi_date_qualifiers(values)
    assert result.pickup_at == datetime(2026, 6, 1, 13, 30)


def test_date_only_values_use_local_noon_before_offset_conversion():
    values = [EdiQualifierValue("X3", date(2026, 6, 1), None, -300)]
    result = resolve_edi_date_qualifiers(values)
    assert result.pickup_at == datetime(2026, 6, 1, 17, 0)


def test_pickup_too_far_before_appointment_snaps_to_appointment():
    values = [
        EdiQualifierValue("10", date(2026, 6, 3), time(8, 0), -300),
        EdiQualifierValue("X3", date(2026, 6, 2), time(18, 59), -300),
    ]
    result = resolve_edi_date_qualifiers(values)
    assert result.pickup_at == datetime(2026, 6, 3, 13, 0)


def test_delivery_six_hours_early_snaps_up_to_pickup():
    values = [
        EdiQualifierValue("X3", date(2026, 6, 4), time(10, 0), 0),
        EdiQualifierValue("D1", date(2026, 6, 4), time(4, 0), 0),
    ]
    result = resolve_edi_date_qualifiers(values)
    assert result.delivery_at == datetime(2026, 6, 4, 10, 0)


def test_delivery_more_than_six_hours_before_pickup_is_rejected():
    values = [
        EdiQualifierValue("X3", date(2026, 6, 4), time(10, 0), 0),
        EdiQualifierValue("D1", date(2026, 6, 4), time(3, 59), 0),
    ]
    with pytest.raises(ValueError):
        resolve_edi_date_qualifiers(values)


def test_stale_tender_older_than_45_days_is_replaced_by_inference():
    values = [
        EdiQualifierValue("X3", date(2026, 6, 10), time(15, 0), 0),
        EdiQualifierValue("86", date(2026, 4, 20), time(9, 0), 0),
    ]
    result = resolve_edi_date_qualifiers(values)
    assert result.tender_at == datetime(2026, 6, 8, 9, 0)


def test_missing_tender_is_inferred_two_days_before_pickup_at_nine_utc():
    values = [EdiQualifierValue("X3", date(2026, 7, 5), time(22, 15), 0)]
    result = resolve_edi_date_qualifiers(values)
    assert result.tender_at == datetime(2026, 7, 3, 9, 0)


def test_invalid_utc_offset_is_rejected():
    values = [EdiQualifierValue("X3", date(2026, 6, 1), time(8, 0), 900)]
    with pytest.raises(ValueError):
        resolve_edi_date_qualifiers(values)
