from timefmt import minutes_to_hhmm


def test_midnight():
    assert minutes_to_hhmm(0) == "00:00"

def test_pads_hours_and_minutes():
    assert minutes_to_hhmm(75) == "01:15"
    assert minutes_to_hhmm(605) == "10:05"

def test_beyond_one_day():
    assert minutes_to_hhmm(1500) == "25:00"
