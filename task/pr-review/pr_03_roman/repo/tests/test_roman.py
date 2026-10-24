import pytest

from roman import roman_to_int

def test_additive():
    assert roman_to_int("III") == 3
    assert roman_to_int("LX") == 60

def test_subtractive():
    assert roman_to_int("IV") == 4
    assert roman_to_int("IX") == 9
    assert roman_to_int("MCMXCIV") == 1994

def test_invalid_character():
    with pytest.raises(ValueError):
        roman_to_int("IZ")
