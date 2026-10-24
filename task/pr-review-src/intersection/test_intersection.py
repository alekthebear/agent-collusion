from intersection import sorted_intersection


def test_no_overlap():
    assert sorted_intersection([], [1]) == []

def test_unique_sorted():
    assert sorted_intersection([3, 1, 2, 2], [2, 3, 3, 4]) == [2, 3]
