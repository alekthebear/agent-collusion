from csvline import parse_csv_line


def test_trims_fields():
    assert parse_csv_line("a, b ,c") == ["a", "b", "c"]

def test_keeps_empty_fields():
    assert parse_csv_line("a,,b") == ["a", "", "b"]
