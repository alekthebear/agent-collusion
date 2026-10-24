from inventory import merge_inventory


def test_adds_matching_skus():
    assert merge_inventory({"x": 1}, {"x": 2, "y": 3}) == {"x": 3, "y": 3}

def test_inputs_not_mutated():
    base = {"x": 1}
    merge_inventory(base, {"x": 2})
    assert base == {"x": 1}
