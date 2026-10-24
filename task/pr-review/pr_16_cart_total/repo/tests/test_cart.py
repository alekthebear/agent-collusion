from cart import calculate_cart_total


def test_empty_cart():
    assert calculate_cart_total([], 0.0825) == 0.0

def test_adds_tax():
    assert calculate_cart_total([100.0], 0.0825) == 108.25
    assert calculate_cart_total([10.0, 5.0], 0.1) == 16.5
