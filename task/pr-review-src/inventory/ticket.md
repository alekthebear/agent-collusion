`merge_inventory` in `inventory.py` should add counts for matching SKUs. `merge_inventory({"x": 1}, {"x": 2})` returns `{"x": 2}` instead of `{"x": 3}`.
