from initials import make_initials


def test_uppercase():
    assert make_initials("ada lovelace") == "A.L"

def test_extra_whitespace():
    assert make_initials("  grace   brewster hopper ") == "G.B.H"
