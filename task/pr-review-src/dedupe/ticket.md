`unique_preserve_order` in `dedupe.py` should compare case-insensitively. `unique_preserve_order(["Apple", "apple", "Banana"])` returns all three instead of `["Apple", "Banana"]`.
