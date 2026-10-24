import re

_PART = re.compile(r"(\d+)([hm])")


def _require_text(text: str) -> str:
    if not isinstance(text, str) or not text or not re.fullmatch(r"(\d+h)?(\d+m)?", text):
        raise ValueError("duration must look like 1h30m, 2h, or 45m")
    return text


def _minutes(amount: int, unit: str) -> int:
    if unit == "h":
        return amount * 60
    return amount


def parse_duration(text: str) -> int:
    """Convert a duration such as "1h30m", "2h", or "45m" to whole minutes."""
    total = 0
    for amount, unit in _PART.findall(_require_text(text)):
        total += _minutes(int(amount), unit)
    return total
