`truncate_text` in `truncate.py` should keep the result, including the `...`, within the limit. `truncate_text("abcdefghij", 8)` returns `"abcdefgh..."` (11 characters) instead of `"abcde..."`.
