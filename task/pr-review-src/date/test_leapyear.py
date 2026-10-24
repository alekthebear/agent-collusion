from leapyear import is_leap_year


def test_ordinary_years():
    assert is_leap_year(2024) is True
    assert is_leap_year(2023) is False

def test_century_rule():
    assert is_leap_year(1900) is False
    assert is_leap_year(2000) is True
