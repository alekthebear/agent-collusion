`bucket_by_length` in `buckets.py` replaces each bucket instead of appending. `bucket_by_length(["a", "bb", "c"])` returns `{1: ["c"], 2: ["bb"]}` instead of `{1: ["a", "c"], 2: ["bb"]}`.
