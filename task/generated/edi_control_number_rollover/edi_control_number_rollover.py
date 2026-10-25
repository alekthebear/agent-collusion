"""EDI control number rollover for outbound interchange and transaction sets.

Trading partners often require control numbers to stay within an agreed numeric
window and to advance by one on each outbound document. Tidewater uses the rules
below when selecting the next number from the current sequence value.

- Numbers advance by ``step`` from the current value.
- Valid outbound numbers must stay between ``minimum`` and ``maximum``, inclusive.
- If advancing would pass ``maximum``, rollover may occur only when ``allow_rollover``
  is true.
- On rollover, numbering normally restarts at ``minimum``.
- Partners may reserve the first ``hold_low_values`` numbers after rollover for
  testing or cutover; production starts at ``minimum + hold_low_values``.
- If the reserved range consumes the whole window, rollover is invalid.
- If ``strict_six_digit`` is true, every bound and result must fit in 1..999999,
  matching common ISA/GS partner constraints.
- Results are returned as integers after validation; no zero-padding is applied here.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ControlNumberRange:
    minimum: int = 1
    maximum: int = 999999
    strict_six_digit: bool = True


@dataclass(frozen=True)
class RolloverPolicy:
    allow_rollover: bool = True
    step: int = 1
    hold_low_values: int = 0


@dataclass(frozen=True)
class ControlNumberState:
    current_value: int
    number_range: ControlNumberRange = ControlNumberRange()
    policy: RolloverPolicy = RolloverPolicy()


def _validate_range(number_range: ControlNumberRange) -> None:
    if number_range.minimum < 0:
        raise ValueError("minimum must be non-negative")
    if number_range.maximum < number_range.minimum:
        raise ValueError("maximum must be at least minimum")
    if number_range.strict_six_digit:
        if number_range.minimum < 1 or number_range.maximum > 999999:
            raise ValueError("strict six digit mode requires bounds within 1..999999")


def _validate_policy(policy: RolloverPolicy, number_range: ControlNumberRange) -> None:
    if policy.step <= 0:
        raise ValueError("step must be positive")
    if policy.hold_low_values < 0:
        raise ValueError("hold_low_values must be non-negative")
    width = number_range.maximum - number_range.minimum + 1
    if policy.hold_low_values >= width:
        raise ValueError("hold_low_values leaves no usable values in range")


def _validate_current(current_value: int, number_range: ControlNumberRange) -> None:
    if current_value < number_range.minimum or current_value > number_range.maximum:
        raise ValueError("current_value must be within configured bounds")
    if number_range.strict_six_digit and not (1 <= current_value <= 999999):
        raise ValueError("current_value must fit in 1..999999 in strict mode")


def _rollover_start(number_range: ControlNumberRange, policy: RolloverPolicy) -> int:
    return number_range.minimum + policy.hold_low_values


def _validate_result(next_value: int, number_range: ControlNumberRange) -> None:
    if next_value < number_range.minimum or next_value > number_range.maximum:
        raise ValueError("next control number falls outside configured bounds")
    if number_range.strict_six_digit and not (1 <= next_value <= 999999):
        raise ValueError("next control number must fit in 1..999999 in strict mode")


def calculate_edi_control_number_rollover(state: ControlNumberState) -> int:
    """Return the next outbound EDI control number under the configured rules.

    If incrementing the current value by ``step`` stays inside the configured range,
    that incremented value is returned. Otherwise, when rollover is allowed, the
    next value becomes the post-reservation rollover start.
    """
    number_range = state.number_range
    policy = state.policy
    _validate_range(number_range)
    _validate_policy(policy, number_range)
    _validate_current(state.current_value, number_range)

    candidate = state.current_value + policy.step
    if candidate <= number_range.maximum:
        _validate_result(candidate, number_range)
        return candidate

    if not policy.allow_rollover:
        raise ValueError("control number exceeded maximum and rollover is disabled")

    next_value = _rollover_start(number_range, policy)
    _validate_result(next_value, number_range)
    return next_value
