"""Preferred shipment references derived from EDI L11 segments.

Tenders and status feeds often carry several L11 references for the same shipment:
PRO,
BOL, customer PO, stop number, work order and other trading-partner identifiers. Our
tracking and billing workflows need one stable, human-facing shortlist. The rules below
score each identifier by qualifier rank, normalize formatting, and then apply customer
exceptions.

Business rules:
- Blank values are ignored after trimming whitespace and collapsing internal spaces.
- Qualifiers are ranked by default as: PRO, BOL, PO, WO, SID, OQ, then everything else.
- References shorter than 3 characters are ignored unless the qualifier is SID.
- Numeric-only references with more than 12 digits are ignored as likely concatenations,
  except PRO allows up to 14 digits.
- Customer ACME prefers PO over PRO when the PO is 6 to 10 characters and not numeric-only.
- Customer HART suppresses PO values starting with "TMP" and prefers BOL over PRO when the
  BOL is exactly 8 digits.
- Duplicate normalized references are collapsed, keeping the best-scoring occurrence.
- Output is at most three references, ordered by highest priority first.
"""

from dataclasses import dataclass

QUALIFIER_RANK = {"PRO": 100, "BOL": 90, "PO": 80, "WO": 70, "SID": 60, "OQ": 50}
MAX_RESULTS = 3


@dataclass(frozen=True)
class L11Reference:
    qualifier: str
    value: str


@dataclass(frozen=True)
class ReferenceContext:
    customer_code: str
    shipment_mode: str = "TL"
    stop_count: int = 1


def _normalize_qualifier(qualifier: str) -> str:
    return qualifier.strip().upper()


def _normalize_value(value: str) -> str:
    return " ".join(value.strip().split())


def _is_numeric(text: str) -> bool:
    return text.isdigit()


def _is_eligible(qualifier: str, value: str) -> bool:
    if not value:
        return False
    if len(value) < 3 and qualifier != "SID":
        return False
    if _is_numeric(value):
        if qualifier == "PRO":
            return len(value) <= 14
        return len(value) <= 12
    return True


def _base_score(qualifier: str, value: str) -> int:
    score = QUALIFIER_RANK.get(qualifier, 10)
    if _is_numeric(value):
        score += 2
    if 6 <= len(value) <= 10:
        score += 1
    return score


def _customer_adjustment(context: ReferenceContext, qualifier: str, value: str) -> int | None:
    customer = context.customer_code.strip().upper()
    if customer == "ACME":
        if qualifier == "PO" and 6 <= len(value) <= 10 and not _is_numeric(value):
            return 30
        if qualifier == "PRO":
            return -15
    if customer == "HART":
        if qualifier == "PO" and value.upper().startswith("TMP"):
            return None
        if qualifier == "BOL" and _is_numeric(value) and len(value) == 8:
            return 20
    if context.shipment_mode.upper() == "LTL" and qualifier == "PRO":
        return 5
    if context.stop_count >= 5 and qualifier == "SID":
        return 8
    return 0


def _score_reference(ref: L11Reference, context: ReferenceContext) -> tuple[int, str, str] | None:
    qualifier = _normalize_qualifier(ref.qualifier)
    value = _normalize_value(ref.value)
    if not _is_eligible(qualifier, value):
        return None
    adjustment = _customer_adjustment(context, qualifier, value)
    if adjustment is None:
        return None
    score = _base_score(qualifier, value) + adjustment
    return score, qualifier, value


def prioritize_edi_l11_references(
    references: list[L11Reference], context: ReferenceContext
) -> list[L11Reference]:
    """Return up to three preferred references in priority order.

    The best occurrence of each normalized value is retained, then all retained values are
    sorted by descending score, qualifier rank tie-breaker, and lexical value.
    """
    best_by_value: dict[str, tuple[int, str]] = {}
    for ref in references:
        scored = _score_reference(ref, context)
        if scored is None:
            continue
        score, qualifier, value = scored
        current = best_by_value.get(value)
        candidate = (score, qualifier)
        if current is None or candidate > current:
            best_by_value[value] = candidate

    ordered = sorted(
        ((score, qualifier, value) for value, (score, qualifier) in best_by_value.items()),
        key=lambda item: (-item[0], -QUALIFIER_RANK.get(item[1], 10), item[2]),
    )
    return [L11Reference(qualifier=qualifier, value=value) for score, qualifier, value in ordered[:MAX_RESULTS]]
