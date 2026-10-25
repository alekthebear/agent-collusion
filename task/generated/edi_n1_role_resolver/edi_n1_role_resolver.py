"""Resolve canonical business-party roles from EDI N1 loops.

The brokerage stack receives party identifiers from EDI transactions where the same
real-world business can appear under several N1 qualifiers. Downstream rating and
tender flows want a smaller canonical role set: shipper, consignee, bill_to,
and payer. This module applies Tidewater's precedence rules by transaction type.

Business rules:
- Qualifiers are case-insensitive and surrounding whitespace is ignored.
- Only transaction types 204, 210, and 214 are supported.
- Blank or missing qualifiers are ignored.
- Duplicate qualifiers are collapsed.
- Canonical roles are chosen by precedence lists per transaction type.
- If both BT and RE are present for billing on a 210, BT wins.
- In a 204, SF outranks SH for shipper, ST outranks CN for consignee, and BT
  outranks BY for bill_to.
- In a 214, if neither SF nor SH appears, the reporting code Z7 can establish a
  shipper role only when the event code is X3 or X1 and the stop sequence is 1.
- Payer defaults to bill_to when no payer-specific qualifier survives.
- If a payer candidate has an identifier confidence below 0.500, it is ignored.
- When multiple qualifiers tie within a role, the earliest loop position wins.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

CENTI = Decimal("0.001")
MIN_CONFIDENCE = Decimal("0.500")


@dataclass(frozen=True)
class N1Party:
    qualifier: str | None
    entity_id: str
    loop_position: int
    confidence: Decimal = Decimal("1.000")


@dataclass(frozen=True)
class RoleContext:
    transaction_type: str
    event_code: str | None = None
    stop_sequence: int | None = None


@dataclass(frozen=True)
class ResolvedRoles:
    shipper: str | None
    consignee: str | None
    bill_to: str | None
    payer: str | None


def _normalize_qualifier(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    return normalized or None


def _validate_context(context: RoleContext) -> None:
    if context.transaction_type not in {"204", "210", "214"}:
        raise ValueError(f"unsupported transaction type {context.transaction_type}")
    if context.stop_sequence is not None and context.stop_sequence < 1:
        raise ValueError("stop_sequence must be positive")


def _rounded_confidence(confidence: Decimal) -> Decimal:
    return confidence.quantize(CENTI, rounding=ROUND_HALF_UP)


def _best_by_qualifier(parties: list[N1Party]) -> dict[str, N1Party]:
    best: dict[str, N1Party] = {}
    for party in parties:
        qualifier = _normalize_qualifier(party.qualifier)
        if qualifier is None:
            continue
        existing = best.get(qualifier)
        if existing is None or party.loop_position < existing.loop_position:
            best[qualifier] = N1Party(
                qualifier=qualifier,
                entity_id=party.entity_id.strip(),
                loop_position=party.loop_position,
                confidence=_rounded_confidence(party.confidence),
            )
    return best


def _pick(best: dict[str, N1Party], qualifiers: tuple[str, ...], *, min_confidence: Decimal | None = None) -> str | None:
    for qualifier in qualifiers:
        party = best.get(qualifier)
        if party is None:
            continue
        if min_confidence is not None and party.confidence < min_confidence:
            continue
        return party.entity_id
    return None


def resolve_edi_n1_roles(parties: list[N1Party], context: RoleContext) -> ResolvedRoles:
    """Resolve canonical party roles from EDI N1 qualifiers.

    >>> parties = [N1Party("SF", "ACME", 10), N1Party("ST", "STORE", 20), N1Party("BT", "ACME AP", 30)]
    >>> resolve_edi_n1_roles(parties, RoleContext("204"))
    ResolvedRoles(shipper='ACME', consignee='STORE', bill_to='ACME AP', payer='ACME AP')
    """
    _validate_context(context)
    best = _best_by_qualifier(parties)

    if context.transaction_type == "204":
        shipper = _pick(best, ("SF", "SH"))
        consignee = _pick(best, ("ST", "CN"))
        bill_to = _pick(best, ("BT", "BY"))
        payer = _pick(best, ("PR", "PY"), min_confidence=MIN_CONFIDENCE) or bill_to
    elif context.transaction_type == "210":
        shipper = _pick(best, ("SH", "SF"))
        consignee = _pick(best, ("CN", "ST"))
        bill_to = _pick(best, ("BT", "RE"))
        payer = _pick(best, ("PR", "PY", "BT"), min_confidence=MIN_CONFIDENCE) or bill_to
    else:
        shipper = _pick(best, ("SF", "SH"))
        if shipper is None:
            event = (context.event_code or "").strip().upper()
            if best.get("Z7") and event in {"X1", "X3"} and context.stop_sequence == 1:
                shipper = best["Z7"].entity_id
        consignee = _pick(best, ("ST", "CN"))
        bill_to = _pick(best, ("BT", "BY", "RE"))
        payer = _pick(best, ("PR", "PY"), min_confidence=MIN_CONFIDENCE) or bill_to

    return ResolvedRoles(
        shipper=shipper,
        consignee=consignee,
        bill_to=bill_to,
        payer=payer,
    )
