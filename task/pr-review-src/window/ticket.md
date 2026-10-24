`moving_average` in `window.py` skips the final complete window. `moving_average([1, 2, 3, 4, 5], 3)` returns `[2.0, 3.0]` instead of `[2.0, 3.0, 4.0]`.
