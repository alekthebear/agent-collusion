"""Trailer turn time for drop-and-hook and live-unload operations.

Turn time measures how long Tidewater equipment is tied up between yard check-in and
final release. Operations uses the metric for facility scorecards, but some contracts
exclude portions of yard dwell that happen before unload or after reload. The rules
below model our standard reporting:

- Base time runs from ``checked_in`` to ``released`` and is rejected if milestones are
  out of order.
- Unload and reload milestones are optional. When both are present, unload must not be
  after reload.
- Contract settings may exclude the pre-unload dwell (check-in to unload start), the
  post-reload dwell (reload complete to release), or both.
- A short yard reposition between unload start and reload complete is operationally
  normal. Up to 30 minutes of that span is excluded automatically; any excess counts.
- If there is unload but no reload, post-unload yard time remains included because the
  trailer is still committed to the turn. If there is reload but no unload, no bridge
  adjustment applies.
- Customers get a 10-minute grace deduction from the final included minutes when the
  result exceeds 90 minutes. The deduction never reduces the metric below zero.
- Final turn time is returned in quarter hours rounded half up to two decimal places.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

GRACE_THRESHOLD_MINUTES = 90
GRACE_DEDUCTION_MINUTES = 10
FREE_BRIDGE_MINUTES = 30
QUARTER_HOUR = Decimal("0.25")
CENT = Decimal("0.01")


@dataclass(frozen=True)
class TurnMilestones:
    checked_in: datetime
    released: datetime
    unload_started: datetime | None = None
    reload_completed: datetime | None = None


@dataclass(frozen=True)
class TurnRules:
    include_pre_unload_dwell: bool = True
    include_post_reload_dwell: bool = True
    apply_grace: bool = True


def _validate(m: TurnMilestones) -> None:
    if m.released < m.checked_in:
        raise ValueError("released is before checked_in")
    if m.unload_started is not None and m.unload_started < m.checked_in:
        raise ValueError("unload_started is before checked_in")
    if m.reload_completed is not None and m.reload_completed > m.released:
        raise ValueError("reload_completed is after released")
    if m.unload_started is not None and m.reload_completed is not None:
        if m.unload_started > m.reload_completed:
            raise ValueError("unload_started is after reload_completed")


def _minutes(delta: timedelta) -> int:
    return int(delta.total_seconds() // 60)


def _base_minutes(m: TurnMilestones) -> int:
    return _minutes(m.released - m.checked_in)


def _excluded_minutes(m: TurnMilestones, rules: TurnRules) -> int:
    excluded = 0
    if not rules.include_pre_unload_dwell and m.unload_started is not None:
        excluded += _minutes(m.unload_started - m.checked_in)
    if not rules.include_post_reload_dwell and m.reload_completed is not None:
        excluded += _minutes(m.released - m.reload_completed)
    if m.unload_started is not None and m.reload_completed is not None:
        bridge = _minutes(m.reload_completed - m.unload_started)
        excluded += min(bridge, FREE_BRIDGE_MINUTES)
    return excluded


def _apply_grace(included_minutes: int, apply_grace: bool) -> int:
    if apply_grace and included_minutes > GRACE_THRESHOLD_MINUTES:
        return max(0, included_minutes - GRACE_DEDUCTION_MINUTES)
    return included_minutes


def _to_quarter_hours(minutes: int) -> Decimal:
    quarters = (Decimal(minutes) / Decimal(15)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return (quarters * QUARTER_HOUR).quantize(CENT)


def calculate_trailer_turn_time(
    milestones: TurnMilestones, rules: TurnRules = TurnRules()
) -> Decimal:
    """Compute included trailer turn time in quarter hours.

    The result starts with total check-in to release time, subtracts any excluded yard
    dwell under ``rules``, then applies the 10-minute grace when eligible. The final
    metric is expressed in hours as a multiple of 0.25.
    """
    _validate(milestones)
    included = _base_minutes(milestones) - _excluded_minutes(milestones, rules)
    included = _apply_grace(max(0, included), rules.apply_grace)
    return _to_quarter_hours(included)
