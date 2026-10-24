from parens import is_balanced_parentheses


def test_nested():
    assert is_balanced_parentheses("(a(b)c)") is True

def test_unclosed():
    assert is_balanced_parentheses("(()") is False

def test_close_before_open():
    assert is_balanced_parentheses(")(") is False
