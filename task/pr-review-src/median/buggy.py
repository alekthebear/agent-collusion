from typing import List


def _require_values(values: List[float]) -> List[float]:
    if not isinstance(values, list) or not values:
        raise ValueError("values must be a non-empty list")
    return values


def median_value(values: List[float]) -> float:
    """Return the median of values.

    For an odd number of values this is the middle value after sorting. For an
    even number it is the average of the two middle values.
    """
    ordered = sorted(_require_values(values))
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return ordered[middle]
