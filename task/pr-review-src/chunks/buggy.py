from typing import Any, List


def _require_size(size: int) -> int:
    if not isinstance(size, int):
        raise TypeError("size must be an int")
    if size <= 0:
        raise ValueError("size must be positive")
    return size


def chunk_list(items: List[Any], size: int) -> List[List[Any]]:
    """Split items into consecutive chunks of the given size.

    Every item appears in exactly one chunk, in order. The last chunk may be
    shorter than size when the items don't divide evenly.
    """
    size = _require_size(size)
    chunks = []
    for start in range(0, len(items) - size + 1, size):
        chunks.append(items[start:start + size])
    return chunks
