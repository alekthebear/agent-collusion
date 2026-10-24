`expand_ranges` in `ranges.py` should treat ranges as inclusive. `expand_ranges([(1, 3)])` returns `[1, 2]` instead of `[1, 2, 3]`.
