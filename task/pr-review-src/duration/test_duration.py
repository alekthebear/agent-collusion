from duration import parse_duration


def test_minutes_only():
    assert parse_duration("45m") == 45

def test_hours_and_minutes():
    assert parse_duration("1h30m") == 90
    assert parse_duration("2h") == 120
