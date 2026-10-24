from transactions import net_by_account


def test_single_transactions():
    assert net_by_account([{"account": "b", "amount": 1}]) == {"b": 1.0}

def test_sums_per_account():
    rows = [
        {"account": "a", "amount": 10},
        {"account": "a", "amount": -2.5},
        {"account": "b", "amount": 1},
    ]
    assert net_by_account(rows) == {"a": 7.5, "b": 1.0}
