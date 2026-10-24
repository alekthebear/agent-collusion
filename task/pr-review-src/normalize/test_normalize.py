from normalize import normalize_scores


def test_spread():
    assert normalize_scores([1, 2, 3]) == [0.0, 0.5, 1.0]

def test_empty():
    assert normalize_scores([]) == []

def test_equal_scores():
    assert normalize_scores([4, 4]) == [0.0, 0.0]
