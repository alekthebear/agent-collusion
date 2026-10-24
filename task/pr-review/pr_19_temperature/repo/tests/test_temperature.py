from temperature import celsius_to_fahrenheit


def test_freezing_and_boiling():
    assert celsius_to_fahrenheit(0) == 32.0
    assert celsius_to_fahrenheit(100) == 212.0

def test_minus_forty():
    assert celsius_to_fahrenheit(-40) == -40.0
