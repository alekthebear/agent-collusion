"""Drayage turn time for marine terminal visits.

Turn time measures how long a driver occupies a terminal for a pickup, drop, or split
move. Operations uses the result for KPI reporting and service review, not billing.
Standard Tidewater rules are: ignore any pre-gate waiting and start the clock at the
later of appointment and in-gate; end at out-gate; subtract a short neutral window for
terminal-caused pauses between completed first-leg work and the second leg of a split
move; classify very short visits as a yard flip minimum; and report hours rounded to the
nearest tenth. Split moves only earn pause relief when both legs completed in the same
visit and the pause is at least 20 minutes, with at most 45 minutes removed.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

MIN_SPLIT_PAUSE = timedelta(minutes=20)
MAX_SPLIT_CREDIT = timedelta(minutes=45)
YARD_FLIP_THRESHOLD = timedelta(minutes=18)
YARD_FLIP_MINIMUM_HOURS = Decimal("0.3")
LONG_VISIT_SURCHARGE_THRESHOLD = timedelta(hours=3, minutes=30)
LONG_VISIT_SURCHARGE_HOURS = Decimal("0.2")
TENTH = Decimal("0.1")
ZERO = Decimal("0.0")


@dataclass(frozen=True)
class TerminalVisit:
    """Milestones for one terminal turn, all in the same local time zone.

    ``appointment`` is optional because many terminals work first-come-first-served.
    For split moves, ``first_leg_complete`` and ``second_leg_start`` capture the neutral
    pause inside the terminal. Both must be present to earn split-pause credit.
    """

    in_gate: datetime
    out_gate: datetime
    appointment: datetime | None = None
    first_leg_complete: datetime | None = None
    second_leg_start: datetime | None = None
    split_move: bool = False
    trouble_window: bool = False


@dataclass(frozen=True)
class TurnTimeRules:
    min_split_pause: timedelta = MIN_SPLIT_PAUSE
    max_split_credit: timedelta = MAX_SPLIT_CREDIT
    yard_flip_threshold: timedelta = YARD_FLIP_THRESHOLD
    yard_flip_minimum_hours: Decimal = YARD_FLIP_MINIMUM_HOURS
    long_visit_threshold: timedelta = LONG_VISIT_SURCHARGE_THRESHOLD
    long_visit_surcharge_hours: Decimal = LONG_VISIT_SURCHARGE_HOURS


def _validate(visit: TerminalVisit) -> None:
    if visit.out_gate < visit.in_gate:
        raise ValueError("out_gate is before in_gate")
    if visit.first_leg_complete is not None and visit.first_leg_complete < visit.in_gate:
        raise ValueError("first_leg_complete is before in_gate")
    if visit.second_leg_start is not None and visit.second_leg_start > visit.out_gate:
        raise ValueError("second_leg_start is after out_gate")
    if visit.first_leg_complete and visit.second_leg_start:
        if visit.second_leg_start < visit.first_leg_complete:
            raise ValueError("second_leg_start is before first_leg_complete")
    if visit.split_move != (visit.first_leg_complete is not None or visit.second_leg_start is not None):
        if visit.split_move or visit.first_leg_complete is not None or visit.second_leg_start is not None:
            raise ValueError("split milestones must be supplied only for split moves and as a complete pair")
    if visit.split_move and (visit.first_leg_complete is None or visit.second_leg_start is None):
        raise ValueError("split moves require first_leg_complete and second_leg_start")


def _clock_start(visit: TerminalVisit) -> datetime:
    if visit.appointment is None:
        return visit.in_gate
    return max(visit.in_gate, visit.appointment)


def _split_credit(visit: TerminalVisit, rules: TurnTimeRules) -> timedelta:
    if not visit.split_move:
        return timedelta(0)
    pause = visit.second_leg_start - visit.first_leg_complete
    if pause < rules.min_split_pause:
        return timedelta(0)
    if pause > rules.max_split_credit:
        return rules.max_split_credit
    return pause


def _base_duration(visit: TerminalVisit, rules: TurnTimeRules) -> timedelta:
    duration = visit.out_gate - _clock_start(visit)
    duration -= _split_credit(visit, rules)
    if duration < timedelta(0):
        return timedelta(0)
    return duration


def calculate_drayage_turn_time(
    visit: TerminalVisit, rules: TurnTimeRules = TurnTimeRules()
) -> Decimal:
    """Turn time in hours, rounded to the nearest tenth.

    Early arrival before an appointment does not count. Split moves may subtract a
    qualifying internal pause of 20 to 45 minutes. Visits shorter than 18 minutes are
    reported as a 0.3 hour yard-flip minimum. Visits at or above 3.5 hours receive a
    0.2 hour trouble-window adder only when ``trouble_window`` is true.
    """
    _validate(visit)
    duration = _base_duration(visit, rules)
    if duration < rules.yard_flip_threshold:
        return rules.yard_flip_minimum_hours
    hours = Decimal(str(duration.total_seconds())) / Decimal("3600")
    if visit.trouble_window and duration >= rules.long_visit_threshold:
        hours += rules.long_visit_surcharge_hours
    return hours.quantize(TENTH, rounding=ROUND_HALF_UP)
