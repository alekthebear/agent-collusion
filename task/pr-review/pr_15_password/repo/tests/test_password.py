from password import is_strong_password


def test_exactly_eight_characters():
    assert is_strong_password("Abcdef1!") is True

def test_longer_password():
    assert is_strong_password("Abcdefg1!") is True

def test_missing_uppercase():
    assert is_strong_password("abcdef1!") is False
