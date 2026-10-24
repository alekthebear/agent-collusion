from word_count import count_words


def test_counts_words():
    assert count_words("a b a") == {"a": 2, "b": 1}

def test_case_insensitive():
    assert count_words("The cat and the hat")["the"] == 2
