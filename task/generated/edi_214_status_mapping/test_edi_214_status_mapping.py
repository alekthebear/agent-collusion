from decimal import Decimal

import pytest

from edi_214_status_mapping import EDI214Event, StatusResult, map_edi_214_status


def test_refused_delivery_overrides_delivered_code():
    event = EDI214Event(event_code="D1", refused_by_consignee=True, proof_of_delivery_signed=True)
    assert map_edi_214_status(event) == StatusResult("delivery_refused", "consignee refused shipment")


def test_exception_note_without_exception_code_marks_delayed():
    event = EDI214Event(event_code="CP", has_exception_note=True, miles_since_last_event=Decimal("12.0"))
    assert map_edi_214_status(event) == StatusResult("delayed", "exception event overrides routine movement")


def test_missed_appointment_code_takes_specific_exception_status():
    event = EDI214Event(event_code="NA")
    assert map_edi_214_status(event) == StatusResult("appointment_missed", "carrier reported missed appointment")


def test_signed_delivery_maps_to_delivered():
    event = EDI214Event(event_code="D1", proof_of_delivery_signed=True)
    assert map_edi_214_status(event) == StatusResult("delivered", "signed proof of delivery received")


def test_unsigned_delivery_maps_to_pending_pod():
    event = EDI214Event(event_code="D1", proof_of_delivery_signed=False)
    assert map_edi_214_status(event) == StatusResult("delivered_pending_pod", "delivery reported without signed POD")


def test_final_stop_arrival_on_site_uses_rounded_distance_threshold():
    event = EDI214Event(event_code="X1", miles_to_stop=Decimal("3.04"), stop_sequence=2, final_stop_sequence=2)
    assert map_edi_214_status(event) == StatusResult("at_delivery", "final stop arrival confirmed on site")


def test_final_stop_arrival_above_threshold_is_near_delivery():
    event = EDI214Event(event_code="X1", miles_to_stop=Decimal("3.05"), stop_sequence=2, final_stop_sequence=2)
    assert map_edi_214_status(event) == StatusResult("near_delivery", "final stop arrival reported but not on site")


def test_arrival_delivery_code_on_intermediate_stop_is_generic_stop_arrival():
    event = EDI214Event(event_code="X1", miles_to_stop=Decimal("1.0"), stop_sequence=1, final_stop_sequence=3)
    assert map_edi_214_status(event) == StatusResult("at_stop", "arrival applies to an intermediate stop")


def test_transit_with_less_than_one_mile_moved_is_stationary():
    event = EDI214Event(event_code="SD", miles_since_last_event=Decimal("0.94"), miles_to_stop=Decimal("40.0"))
    assert map_edi_214_status(event) == StatusResult("stationary", "transit update with less than 1.0 mile moved")


def test_negative_distance_is_rejected():
    with pytest.raises(ValueError):
        map_edi_214_status(EDI214Event(event_code="CP", miles_to_stop=Decimal("-0.1")))
