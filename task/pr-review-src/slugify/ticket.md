`slugify_title` in `slugify.py` should collapse runs of spaces and hyphens into one hyphen. `slugify_title("Hello -- World")` returns `"hello---world"` instead of `"hello-world"`.
