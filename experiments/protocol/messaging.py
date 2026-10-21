"""Inter-agent messaging and per-agent raw-log retrieval."""

import json
from typing import Any

from experiments.protocol.errors import error_string
from experiments.protocol.group import GROUP_CHAT
from experiments.protocol.state import _log_event, agent_state, display_name


def _send_message(
    state: dict[str, Any],
    actor: str,
    content: str,
    message_type: str = "other",
    to: str | None = None,
) -> dict[str, Any]:
    """Deliver one message to the turn's recipient.

    With private links in a larger group, the sender names the recipient with
    ``to``, which must be the agent the turn is for. A pair has one possible
    recipient, and a group-chat post reaches every other agent; neither takes ``to``.
    """
    slot = agent_state(state, actor)
    group = state["group"]
    recipient = state["recipient"]
    if slot["delivered"]:
        if group.is_pair:
            error = f"{actor} already sent its one message for this round"
        elif recipient == GROUP_CHAT:
            error = "you already sent this turn's message. Each turn carries one message."
        else:
            error = (
                f"you already sent this turn's message, to "
                f"{display_name(recipient)}. Each turn carries one message; a "
                "message to another agent goes in your turn with them."
            )
        return _reject_message(
            state=state,
            actor=actor,
            content=content,
            message_type=message_type,
            error=error_string("MessageError", error),
            to=to,
        )

    if not group.is_pair and recipient != GROUP_CHAT and to != recipient:
        named = display_name(to) if to in group.agent_ids else repr(to)
        return _reject_message(
            state=state,
            actor=actor,
            content=content,
            message_type=message_type,
            error=error_string(
                "MessageError",
                f"this turn's message goes to {display_name(recipient)}, not "
                f"{named}. A message to another agent goes in your turn with them.",
            ),
            to=to,
        )

    if (
        state["throttled"]
        and len(content) > state["char_limit"]
    ):
        return _reject_message(
            state=state,
            actor=actor,
            content=content,
            message_type=message_type,
            error=error_string(
                "MessageError", f"exceeds {state['char_limit']} char limit"
            ),
            to=to,
        )

    slot["delivered"] = True
    # Keep the originating 0-based round; display tags add one.
    payload: dict[str, Any] = {
        "from": actor,
        "to": recipient,
        "content": content,
        "round": state["round"],
    }
    payload["message_type"] = message_type
    # Deliver immediately so the recipient can reply within the same round.
    recipients = (
        [a for a in group.agent_ids if a != actor]
        if recipient == GROUP_CHAT
        else [recipient]
    )
    for agent_id in recipients:
        agent_state(state, agent_id)["inbox"].append(dict(payload))

    result = {"success": True, "chars_sent": len(content)}
    event = {
        "actor": actor,
        "recipient": recipient,
        "tool": "send_message",
        "success": True,
        "content": content,
    }
    event["message_type"] = message_type
    if not group.is_pair and recipient != GROUP_CHAT:
        event["to"] = to
    _log_event(state, event)
    return result


def _reject_message(
    *,
    state: dict[str, Any],
    actor: str,
    content: str,
    message_type: str,
    error: str,
    to: str | None = None,
) -> dict[str, Any]:
    result = {"success": False, "error": error, "chars_sent": 0}
    # Record the complete attempted message, including refused deliveries.
    event = {
        "actor": actor,
        "recipient": state["recipient"],
        "tool": "send_message",
        "success": False,
        "error": error,
        "content": content,
    }
    event["message_type"] = message_type
    if not state["group"].is_pair and state["recipient"] != GROUP_CHAT:
        # What the sender asked for, beside the turn's actual recipient.
        event["to"] = to
    _log_event(state, event)
    return result


def _format_private_raw_log(slot: dict[str, Any]) -> str:
    return json.dumps(
        slot.get("private_raw_log", []),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _get_log(state: dict[str, Any], actor: str) -> dict[str, Any]:
    """Return only the calling agent's raw log.

    The dispatch gate permits one retrieval per agent per episode.
    """
    slot = agent_state(state, actor)
    raw_log = _format_private_raw_log(slot)
    slot["private_raw_log_retrieved"] = True
    result = {
        "success": True,
        "raw_log": raw_log,
        "raw_log_chars": len(raw_log),
    }
    _log_event(
        state,
        {
            "actor": actor,
            "tool": "get_log",
            "success": True,
        },
    )
    return result
