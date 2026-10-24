_ELLIPSIS = "..."


def _require_limit(limit: int) -> int:
    if not isinstance(limit, int) or limit <= len(_ELLIPSIS):
        raise ValueError("limit must be an int greater than 3")
    return limit


def truncate_text(text: str, limit: int) -> str:
    """Shorten text to at most limit characters, ending with "..." when cut.

    Text that already fits is returned unchanged. When text is cut, the result,
    including the ellipsis, is exactly limit characters long.
    """
    limit = _require_limit(limit)
    if len(text) <= limit:
        return text
    return text[:limit] + _ELLIPSIS
