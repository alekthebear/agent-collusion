from compact import compact_whitespace


def test_strips_lines():
    assert compact_whitespace(["  a ", "b  "]) == ["a", "b"]

def test_drops_blank_lines():
    assert compact_whitespace(["  a ", "", "   ", "b"]) == ["a", "b"]
