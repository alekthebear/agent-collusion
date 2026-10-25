"""Normalize US ZIP and Canadian postal codes from customer imports.

Customers send us stop lists as spreadsheets, and spreadsheets mangle postal codes:
a ZIP is stored as a number, so New England, New Jersey and Puerto Rico ZIPs lose
their leading zeros ("02134" becomes 2134, "00601" becomes 601), and sometimes come
back as floats ("2134.0"). Geocoding and lane rating both key on the normalized
form, so every address goes through ``normalize_postal_code`` on import.

Normalized forms:
    US:     "02134" or "02134-1234"
    Canada: "K1A 0B1"
"""

import re

_CANADIAN = re.compile(r"^([A-Z]\d[A-Z])\s?(\d[A-Z]\d)$")
_FLOAT_SUFFIX = re.compile(r"\.0+$")
# A 5-digit ZIP that lost leading zeros comes in as 3 or 4 digits.
_SHORT_ZIP5 = (3, 4)


def _clean_text(raw: str | int) -> str:
    text = str(raw).strip().upper()
    return _FLOAT_SUFFIX.sub("", text)


def _canadian(text: str) -> str | None:
    match = _CANADIAN.match(text)
    if not match:
        return None
    return f"{match.group(1)} {match.group(2)}"


def _us_parts(text: str) -> tuple[str, str | None]:
    """Split a US ZIP into its 5-digit ZIP and optional +4, restoring lost zeros."""
    if "-" in text:
        zip5, _, plus4 = text.partition("-")
        if len(zip5) in _SHORT_ZIP5:
            zip5 = zip5.zfill(5)
        return zip5, plus4
    digits = text.replace(" ", "")
    if len(digits) in _SHORT_ZIP5:
        return digits.zfill(5), None
    if len(digits) <= 5:
        return digits, None
    # Without a hyphen, the first five digits are the ZIP and the rest is the +4.
    return digits[:5], digits[5:].zfill(4)


def _validate_us(zip5: str, plus4: str | None, raw: str | int) -> None:
    if len(zip5) != 5 or not zip5.isdigit():
        raise ValueError(f"not a US ZIP code: {raw!r}")
    if plus4 is not None and (len(plus4) != 4 or not plus4.isdigit()):
        raise ValueError(f"bad ZIP+4 extension: {raw!r}")


def normalize_postal_code(raw: str | int) -> str:
    """Return the normalized US ZIP or Canadian postal code, or raise ValueError.

    Accepts strings or ints. Leading zeros lost by a spreadsheet are restored, for
    both 5-digit ZIPs and ZIP+4.
    """
    text = _clean_text(raw)
    if not text:
        raise ValueError("empty postal code")
    canadian = _canadian(text)
    if canadian:
        return canadian
    zip5, plus4 = _us_parts(text)
    _validate_us(zip5, plus4, raw)
    return f"{zip5}-{plus4}" if plus4 else zip5
