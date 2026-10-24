from acronym import make_acronym


def test_uppercase():
    assert make_acronym("portable network graphics") == "PNG"

def test_hyphenated_words():
    assert make_acronym("central-processing unit") == "CPU"
