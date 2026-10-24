from topn import top_n


def test_descending_order():
    assert top_n([3, 1, 2], 2) == [3, 2]

def test_n_larger_than_input():
    assert top_n([5, 5, 1], 5) == [5, 5, 1]

def test_zero():
    assert top_n([1, 2], 0) == []
