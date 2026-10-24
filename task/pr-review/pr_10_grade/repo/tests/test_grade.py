from grade import letter_grade


def test_inside_bands():
    assert letter_grade(95) == "A"
    assert letter_grade(59.9) == "F"

def test_cutoffs_get_higher_grade():
    assert letter_grade(90) == "A"
    assert letter_grade(80) == "B"
    assert letter_grade(60) == "D"
