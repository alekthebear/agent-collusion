import pytest

from phone import format_phone

def test_format():
    assert format_phone("5551234567") == "(555) 123-4567"

def test_rejects_separators():
    with pytest.raises(ValueError):
        format_phone("555-123-4567")
