from decimal import Decimal

import pytest

from edi_segment_count import PartnerProfile, SegmentBatch, calculate_edi_segment_count


def test_counts_st_through_se_inclusive():
    batch = SegmentBatch(("ST*204*0001", "B2*DATA", "SE*3*0001"))
    assert calculate_edi_segment_count(batch) == 3


def test_ignores_segments_before_st_and_after_se():
    batch = SegmentBatch(("ISA*00", "GS*SM", "ST*204*0001", "B2*DATA", "SE*3*0001", "GE*1", "IEA*1"))
    assert calculate_edi_segment_count(batch) == 3


def test_ignores_blank_and_whitespace_entries():
    batch = SegmentBatch((" ", "ST*204*0001", "", "B2*DATA", "   ", "SE*3*0001", "\t"))
    assert calculate_edi_segment_count(batch) == 3


def test_first_st_and_last_se_define_envelope():
    batch = SegmentBatch(("ST*204*0001", "B2*DATA", "ST*EXTRA", "LX*1", "SE*2*JUNK", "SE*5*0001"))
    assert calculate_edi_segment_count(batch) == 6


def test_nte_after_se_is_not_counted():
    batch = SegmentBatch(("ST*204*0001", "B2*DATA", "SE*3*0001", "NTE*TRAILER*note"))
    assert calculate_edi_segment_count(batch) == 3


def test_nte_inside_envelope_is_counted():
    batch = SegmentBatch(("ST*204*0001", "NTE*ADD*note", "SE*3*0001"))
    assert calculate_edi_segment_count(batch) == 3


def test_missing_st_raises_value_error():
    with pytest.raises(ValueError):
        calculate_edi_segment_count(SegmentBatch(("B2*DATA", "SE*2*0001")))


def test_missing_se_raises_value_error():
    with pytest.raises(ValueError):
        calculate_edi_segment_count(SegmentBatch(("ST*204*0001", "B2*DATA")))


def test_count_over_max_is_rejected():
    batch = SegmentBatch(("ST*204*0001", "B2*DATA", "SE*3*0001"))
    with pytest.raises(ValueError):
        calculate_edi_segment_count(batch, PartnerProfile(max_segments=2))
