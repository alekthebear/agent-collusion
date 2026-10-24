from pagination import paginate


ITEMS = [1, 2, 3, 4, 5]

def test_first_page():
    assert paginate(ITEMS, 1, 2) == [1, 2]

def test_last_partial_page():
    assert paginate(ITEMS, 3, 2) == [5]

def test_past_the_end():
    assert paginate(ITEMS, 4, 2) == []
