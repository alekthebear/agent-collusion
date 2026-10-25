"""Normalize bill-of-lading references from raw strings.

The settlement pipeline receives reference strings copied from shipper paperwork and EDI.
This parser extracts stable reference components so matching can ignore punctuation,
spacing, repeated labels, and scanner noise. Business rules:

- Empty tokens and tokens with no letters or digits are ignored.
- Known labels map to canonical prefixes: ``BOL``, ``PO``, ``SO``, and ``PU``.
- A token like ``BOL12345`` or ``PO-7788`` becomes one prefixed reference when the
  prefix is recognized and the remainder is valid.
- Numeric payloads drop leading zeros unless the whole value is zero. Alphanumeric
  payloads keep internal zeros.
- Payloads shorter than 3 characters are ignored, except ``PO`` allows 1 and ``PU``
  allows 1 because some customers use short order and pickup numbers.
- Payloads longer than 12 characters are ignored unless they are all digits, in which
  case the last 12 digits are kept; this handles overflowed scans.
- Duplicate normalized references are suppressed in first-seen order.
- A bare token with no recognizable prefix is treated as ``BOL`` only when it is all
  digits and has normalized length 3 to 10 inclusive.
"""

from dataclasses import dataclass

LABELS = {
    "BOL": "BOL",
    "BILL": "BOL",
    "BILL OF LADING": "BOL",
    "BILL-OF-LADING": "BOL",
    "PO": "PO",
    "P/O": "PO",
    "PURCHASE ORDER": "PO",
    "SO": "SO",
    "SHIPPER ORDER": "SO",
    "PU": "PU",
    "PICKUP": "PU",
}
MIN_LEN = {"BOL": 3, "PO": 1, "SO": 3, "PU": 1}
MAX_LEN = 12
SEPARATORS = " :-#/\\"


@dataclass(frozen=True)
class RawReferenceSet:
    references: tuple[str, ...]


@dataclass(frozen=True)
class ParsedReference:
    prefix: str
    value: str


def _clean(text: str) -> str:
    return " ".join(text.strip().upper().split())


def _payload_chars(text: str) -> str:
    return "".join(ch for ch in text if ch.isalnum())


def _normalize_value(prefix: str, value: str) -> str | None:
    raw = _payload_chars(value)
    if not raw:
        return None
    if raw.isdigit():
        raw = raw.lstrip("0") or "0"
    if len(raw) > MAX_LEN:
        if raw.isdigit():
            raw = raw[-MAX_LEN:]
        else:
            return None
    if len(raw) < MIN_LEN[prefix]:
        return None
    return raw


def _split_prefixed_token(token: str) -> tuple[str, str] | None:
    compact = _clean(token)
    for label, prefix in sorted(LABELS.items(), key=lambda item: len(item[0]), reverse=True):
        if compact == label:
            return None
        if compact.startswith(label):
            remainder = compact[len(label):].lstrip(SEPARATORS)
            if remainder:
                return prefix, remainder
    return None


def _extract_one(token: str, pending_prefix: str | None) -> tuple[ParsedReference | None, str | None]:
    cleaned = _clean(token)
    if not cleaned:
        return None, pending_prefix
    if cleaned in LABELS:
        return None, LABELS[cleaned]
    combined = _split_prefixed_token(cleaned)
    if combined is not None:
        prefix, remainder = combined
        value = _normalize_value(prefix, remainder)
        return (ParsedReference(prefix, value) if value else None), None
    if pending_prefix is not None:
        value = _normalize_value(pending_prefix, cleaned)
        return (ParsedReference(pending_prefix, value) if value else None), None
    raw = _payload_chars(cleaned)
    if raw.isdigit():
        normalized = raw.lstrip("0") or "0"
        if 3 <= len(normalized) <= 10:
            return ParsedReference("BOL", normalized), None
    return None, None


def parse_bol_references(raw: RawReferenceSet) -> tuple[ParsedReference, ...]:
    """Return unique normalized reference components in first-seen order."""
    seen: set[tuple[str, str]] = set()
    parsed: list[ParsedReference] = []
    pending_prefix: str | None = None
    for token in raw.references:
        item, pending_prefix = _extract_one(token, pending_prefix)
        if item is None:
            continue
        key = (item.prefix, item.value)
        if key in seen:
            continue
        seen.add(key)
        parsed.append(item)
    return tuple(parsed)
