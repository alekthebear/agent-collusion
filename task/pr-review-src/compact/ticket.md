`compact_whitespace` in `compact.py` should drop lines that are empty after stripping. `compact_whitespace(["  a ", "", "   ", "b"])` returns `["a", "", "", "b"]` instead of `["a", "b"]`.
