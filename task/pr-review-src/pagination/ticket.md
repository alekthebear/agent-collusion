`paginate` in `pagination.py` treats pages as 0-indexed. `paginate([1, 2, 3, 4, 5], 1, 2)` returns `[3, 4]` instead of `[1, 2]`.
