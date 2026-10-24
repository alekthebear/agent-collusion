from buckets import bucket_by_length


def test_groups_in_order():
    assert bucket_by_length(["a", "bb", "c", ""]) == {1: ["a", "c"], 2: ["bb"], 0: [""]}
