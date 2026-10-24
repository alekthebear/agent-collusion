import pytest

from postal_codes import normalize_postal_code


def test_five_digit_zip_is_unchanged():
    assert normalize_postal_code("97209") == "97209"
    assert normalize_postal_code(" 97209 ") == "97209"


def test_lost_leading_zeros_are_restored():
    assert normalize_postal_code(2134) == "02134"
    assert normalize_postal_code("601") == "00601"
    assert normalize_postal_code("2134.0") == "02134"


def test_zip_plus_four_with_hyphen():
    assert normalize_postal_code("02134-1234") == "02134-1234"
    assert normalize_postal_code("2134-1234") == "02134-1234"


def test_nine_digits_without_hyphen():
    assert normalize_postal_code("972091234") == "97209-1234"
    assert normalize_postal_code(972091234) == "97209-1234"


def test_canadian_postal_codes():
    assert normalize_postal_code("k1a0b1") == "K1A 0B1"
    assert normalize_postal_code(" M5V 3L9 ") == "M5V 3L9"


def test_garbage_is_rejected():
    for raw in ("", "ABCDE", "1234567890", "02134-12"):
        with pytest.raises(ValueError):
            normalize_postal_code(raw)


def test_zip_plus_four_that_lost_a_zero():
    assert normalize_postal_code("21341234") == "02134-1234"


def test_numeric_zip_plus_four_from_spreadsheet():
    assert normalize_postal_code(21341234) == "02134-1234"
    assert normalize_postal_code("8601234.0") == "00860-1234"
