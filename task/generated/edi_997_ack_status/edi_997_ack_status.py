"""Functional acknowledgment status for outbound EDI 997 processing.

Tidewater treats one 997 at the functional-group level and classifies it into a
single operational outcome for settlement and support dashboards. The source feed
provides how many transaction sets were accepted and rejected plus control counts
copied from the interchange.

Business rules:
- ``accepted_count`` and ``rejected_count`` are non-negative whole transaction counts.
- ``included_count`` is the number of transaction sets reported in AK9/SE and must be
  at least the sum of accepted and rejected transactions. Extra included sets are
  allowed only up to a configured tolerance to cover partner mapping quirks.
- If nothing is included, the acknowledgment is ``EMPTY``.
- If accepted and rejected are both zero while included is positive, the outcome is
  ``RECEIVED_NOT_CLASSIFIED``. This special case is treated separately from count
  balancing because some partners return a receipt-level 997 before classifying
  individual transaction sets.
- A balanced acknowledgment with no rejects is ``ACCEPTED``.
- A balanced acknowledgment with both accepted and rejected transactions is
  ``PARTIALLY_ACCEPTED``.
- A balanced acknowledgment with zero accepts and one or more rejects is ``REJECTED``.
- Control-number balancing is required unless the partner is flagged lenient. The
  absolute difference between ``group_control_sent`` and ``group_control_received``
  may not exceed ``allowed_control_gap``. When the gap exceeds the limit, the status
  is ``CONTROL_MISMATCH`` regardless of transaction counts.
- Any overage beyond the accepted+rejected total is measured as a rate of included
  transactions and rounded half up to four decimals before comparing to the tolerance.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

FOUR_PLACES = Decimal("0.0001")
DEFAULT_OVERAGE_TOLERANCE = Decimal("0.0200")


@dataclass(frozen=True)
class AckCounts:
    accepted_count: int
    rejected_count: int
    included_count: int


@dataclass(frozen=True)
class ControlBalance:
    group_control_sent: int
    group_control_received: int
    allowed_control_gap: int = 0
    lenient_partner: bool = False


@dataclass(frozen=True)
class AckPolicy:
    overage_tolerance: Decimal = DEFAULT_OVERAGE_TOLERANCE


def _validate_counts(counts: AckCounts) -> None:
    for name, value in (
        ("accepted_count", counts.accepted_count),
        ("rejected_count", counts.rejected_count),
        ("included_count", counts.included_count),
    ):
        if value < 0:
            raise ValueError(f"{name} must be non-negative")


def _validate_control(control: ControlBalance) -> None:
    if control.allowed_control_gap < 0:
        raise ValueError("allowed_control_gap must be non-negative")


def _validate_policy(policy: AckPolicy) -> None:
    if policy.overage_tolerance < Decimal("0") or policy.overage_tolerance > Decimal("1"):
        raise ValueError("overage_tolerance must be between 0 and 1")


def _control_is_balanced(control: ControlBalance) -> bool:
    if control.lenient_partner:
        return True
    return abs(control.group_control_sent - control.group_control_received) <= control.allowed_control_gap


def _overage_rate(counts: AckCounts) -> Decimal:
    classified = counts.accepted_count + counts.rejected_count
    extra = counts.included_count - classified
    if extra <= 0 or counts.included_count == 0:
        return Decimal("0.0000")
    rate = Decimal(extra) / Decimal(counts.included_count)
    return rate.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def _counts_are_consistent(counts: AckCounts, policy: AckPolicy) -> bool:
    classified = counts.accepted_count + counts.rejected_count
    if classified > counts.included_count:
        return False
    return _overage_rate(counts) <= policy.overage_tolerance


def calculate_edi_997_ack_status(
    counts: AckCounts,
    control: ControlBalance,
    policy: AckPolicy = AckPolicy(),
) -> str:
    """Return the operational status for one functional acknowledgment.

    >>> counts = AckCounts(accepted_count=8, rejected_count=0, included_count=8)
    >>> control = ControlBalance(group_control_sent=105, group_control_received=105)
    >>> calculate_edi_997_ack_status(counts, control)
    'ACCEPTED'
    """
    _validate_counts(counts)
    _validate_control(control)
    _validate_policy(policy)

    if not _control_is_balanced(control):
        return "CONTROL_MISMATCH"

    if counts.included_count == 0:
        return "EMPTY"

    if counts.accepted_count == 0 and counts.rejected_count == 0:
        return "RECEIVED_NOT_CLASSIFIED"

    if not _counts_are_consistent(counts, policy):
        return "COUNT_MISMATCH"

    if counts.rejected_count == 0:
        return "ACCEPTED"

    if counts.accepted_count == 0:
        return "REJECTED"

    return "PARTIALLY_ACCEPTED"
