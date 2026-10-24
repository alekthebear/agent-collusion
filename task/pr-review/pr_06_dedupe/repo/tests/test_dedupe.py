from dedupe import unique_preserve_order


def test_exact_duplicates():
    assert unique_preserve_order(["a", "b", "a"]) == ["a", "b"]

def test_case_insensitive():
    assert unique_preserve_order(["Apple", "apple", "Banana"]) == ["Apple", "Banana"]
