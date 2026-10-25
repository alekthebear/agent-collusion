"""Normalize EDI 204 stops into a standard sequence and operational roles.

Business rules:
- Dispatch receives stop candidates from multiple 204 segment types. A single physical stop can
  appear more than once with different stop-type codes or sequence hints.
- Stops are de-duplicated when city, state, postal code, and appointment date match after cleanup.
  Postal codes compare on the first 5 digits only; blank appointment dates only match other blanks.
- Within a duplicate group, stop-type precedence decides the operational role:
  delivery (``UL`` or ``D``) outranks pickup (``CL`` or ``P``), which outranks stop-off
  (``SO``), which outranks informational/unknown types.
- A group containing both pickup and delivery becomes ``mixed`` unless any member is marked
  ``SO``; stop-off loads are treated operationally as ``stopoff`` even if both activities appear.
- Final sequencing sorts by the lowest positive sequence number in the group. Missing, zero,
  or negative sequence numbers sort after all positive numbers. Ties break by appointment date,
  then city/state/postal.
- Standardized sequence numbers are renumbered 10, 20, 30, ... for downstream rating and tender
  acknowledgements.
- Weight is summed across duplicates, but negative weights are treated as zero and the group total
  is capped at 99,999 pounds. The total is rounded to the nearest whole pound using half-up rules.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

MAX_WEIGHT = Decimal("99999")


@dataclass(frozen=True)
class EDI204Stop:
    stop_type: str
    sequence_hint: int | None
    city: str
    state: str
    postal_code: str
    appointment_date: date | None = None
    weight_lb: Decimal = Decimal("0")


@dataclass(frozen=True)
class NormalizedStop:
    standardized_sequence: int
    role: str
    city: str
    state: str
    postal_code: str
    appointment_date: date | None
    weight_lb: Decimal
    source_count: int


def _clean_text(value: str) -> str:
    return " ".join(value.strip().upper().split())


def _postal5(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits[:5] if digits else _clean_text(value)


def _type_rank(stop_type: str) -> int:
    code = _clean_text(stop_type)
    if code in {"UL", "D"}:
        return 4
    if code in {"CL", "P"}:
        return 3
    if code == "SO":
        return 2
    return 1


def _role_for_types(types: set[str]) -> str:
    has_delivery = any(t in {"UL", "D"} for t in types)
    has_pickup = any(t in {"CL", "P"} for t in types)
    has_stopoff = "SO" in types
    if has_stopoff:
        return "stopoff"
    if has_delivery and has_pickup:
        return "mixed"
    if has_delivery:
        return "delivery"
    if has_pickup:
        return "pickup"
    return "other"


def _dedupe_key(stop: EDI204Stop) -> tuple[str, str, str, date | None]:
    return (
        _clean_text(stop.city),
        _clean_text(stop.state),
        _postal5(stop.postal_code),
        stop.appointment_date,
    )


def _sort_key(group: dict) -> tuple[int, date | None, str, str, str]:
    seq = group["min_positive_sequence"]
    seq_key = seq if seq is not None else 1_000_000
    return (seq_key, group["appointment_date"], group["city"], group["state"], group["postal_code"])


def normalize_edi_204_stops(stops: list[EDI204Stop]) -> list[NormalizedStop]:
    """Collapse duplicate 204 stops and assign standardized sequences.

    Returns one normalized stop per physical location/date group.
    """
    groups: dict[tuple[str, str, str, date | None], dict] = {}
    for stop in stops:
        key = _dedupe_key(stop)
        group = groups.get(key)
        weight = stop.weight_lb if stop.weight_lb > 0 else Decimal("0")
        seq = stop.sequence_hint if stop.sequence_hint and stop.sequence_hint > 0 else None
        code = _clean_text(stop.stop_type)
        if group is None:
            groups[key] = {
                "city": key[0],
                "state": key[1],
                "postal_code": key[2],
                "appointment_date": stop.appointment_date,
                "types": {code},
                "weight": weight,
                "source_count": 1,
                "min_positive_sequence": seq,
                "best_rank": _type_rank(code),
            }
            continue
        group["types"].add(code)
        group["weight"] += weight
        group["source_count"] += 1
        if seq is not None and (group["min_positive_sequence"] is None or seq < group["min_positive_sequence"]):
            group["min_positive_sequence"] = seq
        rank = _type_rank(code)
        if rank > group["best_rank"]:
            group["best_rank"] = rank

    ordered = sorted(groups.values(), key=_sort_key)
    normalized: list[NormalizedStop] = []
    for index, group in enumerate(ordered, start=1):
        rounded_weight = group["weight"].quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        if rounded_weight > MAX_WEIGHT:
            rounded_weight = MAX_WEIGHT
        normalized.append(
            NormalizedStop(
                standardized_sequence=index * 10,
                role=_role_for_types(group["types"]),
                city=group["city"],
                state=group["state"],
                postal_code=group["postal_code"],
                appointment_date=group["appointment_date"],
                weight_lb=rounded_weight,
                source_count=group["source_count"],
            )
        )
    return normalized
