from truncate import truncate_text


def test_short_text_unchanged():
    assert truncate_text("abc", 8) == "abc"

def test_within_limit():
    assert truncate_text("abcdefghij", 8) == "abcde..."
    assert len(truncate_text("x" * 50, 10)) == 10
