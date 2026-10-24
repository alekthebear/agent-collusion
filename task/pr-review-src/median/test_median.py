from median import median_value


def test_odd_length():
    assert median_value([3, 1, 2]) == 2

def test_even_length():
    assert median_value([1, 2, 3, 4]) == 2.5
    assert median_value([4, 1]) == 2.5
