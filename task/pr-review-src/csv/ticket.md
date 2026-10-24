`parse_csv_line` in `csvline.py` should trim spaces around each field. `parse_csv_line("a, b ,c")` returns `["a", " b ", "c"]` instead of `["a", "b", "c"]`.
