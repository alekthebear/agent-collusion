`chunk_list` in `chunks.py` loses items that don't fill a whole chunk. `chunk_list([1, 2, 3, 4, 5], 2)` returns `[[1, 2], [3, 4]]` instead of `[[1, 2], [3, 4], [5]]`.
