from ranges import expand_ranges


def test_inclusive():
    assert expand_ranges([(1, 3)]) == [1, 2, 3]

def test_sorted_after_expanding():
    assert expand_ranges([(5, 6), (1, 2)]) == [1, 2, 5, 6]
