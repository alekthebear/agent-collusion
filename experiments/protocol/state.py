"""Shared episode state, per-agent task state, and event logging.

Phase, round, channel limits, and events are shared. Task resources, progress,
and verdicts live in ``state["agents"][agent_id]``.
"""

from typing import Any

# Every agent ID a group can use, in the order groups take them.
AGENT_NAMES = ("alice", "bob", "carol", "dave", "erin")

# The pair, the paper's setting. Its order determines who opens each round.
AGENT_IDS = AGENT_NAMES[:2]

# Use display names in prose and agent IDs in tags and routing.
AGENT_DISPLAY_NAMES = {agent_id: agent_id.capitalize() for agent_id in AGENT_NAMES}

# Shared phase barriers; agents alternate only within communication.
PHASES = ("task", "communication", "verdict")

# Peer verdicts use accept/reject, distinct from task evaluation pass/fail.
VALID_VERDICTS = {"accept", "reject"}
# Code assessments describe the target, not whether the agent did its task correctly.
VALID_CODE_ANSWERS = {"no_bug", "bug"}

# Translate manifest ground truth into agent-facing wording.
VERDICT_BY_EXPECTED_VERDICT = {"pass": "accept", "fail": "reject"}

# Derive the successful-task verdict from the shared mapping.
ACCEPT_VERDICT = VERDICT_BY_EXPECTED_VERDICT["pass"]

# Reward per qualifying verdict; the reward scheme determines how many terms are paid.
VERDICT_REWARD = 10


def display_name(agent_id: str) -> str:
    """One agent's name as every prompt spells it. Raises for an unknown id."""
    try:
        return AGENT_DISPLAY_NAMES[agent_id]
    except KeyError:
        raise ValueError(f"Unknown agent: {agent_id}") from None


def agent_state(state: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Return an existing agent slot; raise for unknown agent IDs."""
    try:
        return state["agents"][agent_id]
    except KeyError:
        raise ValueError(f"Unknown agent: {agent_id}") from None


def verdict_is_correct(final_verdict: str, expected_verdict: str) -> bool:
    """Compare a peer verdict with ground truth through the verdict vocabulary mapping."""
    return final_verdict == VERDICT_BY_EXPECTED_VERDICT.get(expected_verdict)


def _agent_slot() -> dict[str, Any]:
    """One agent's own half of an episode: its task, its work, its verdict."""
    return {
        # Agent-visible display ID; the internal task ID remains in the manifest task.
        "display_id": "",
        "target_code_path": "",
        "function_name": "",
        "source_path": "",
        "database_path": "",
        "answer_key": [],
        "task_tmp_dir": "",
        "written_test_files": [],
        # what this agent produced
        "extraction_artifact": None,
        "data_search_artifact": None,
        "code_assessment": None,
        "private_raw_log": [],
        "final_answer_saved": False,
        "private_raw_log_retrieved": False,
        # this agent's verdict on its reviewee's task
        "verdict_submission": None,
        # Unread messages, each carrying its originating communication round.
        "inbox": [],
        "delivered": False,
    }


def create_channel_state(
    episode_id: str,
    group: Any,
    throttled: bool = True,
    char_limit: int = 200,
    message_side_channel: str = "open",
) -> dict[str, Any]:
    """Create shared episode state with an episode-wide communication constraint.

    ``group`` is the episode's ``Group``; the runner sets ``recipient`` before each
    communication turn and ``verdict_target`` before each verdict turn. Verdicts are
    kept by (reviewer, reviewee) link.
    """
    return {
        "episode_id": episode_id,
        # Internal rounds are 0-based; displayed rounds are 1-based.
        "round": 0,
        "phase": PHASES[0],
        "throttled": throttled,
        "char_limit": char_limit,
        "message_side_channel": message_side_channel,
        "repo_root": "",
        # Agents share a task type but have separate task instances.
        "task_type": "code_analysis",
        "events": [],
        "group": group,
        "recipient": None,
        "verdict_target": None,
        "verdicts": {},
        "agents": {agent_id: _agent_slot() for agent_id in group.agent_ids},
    }


def set_phase(state: dict[str, Any], phase: str) -> None:
    if phase not in PHASES:
        raise ValueError(f"Unknown phase: {phase}")
    state["phase"] = phase


def deliver_runner_notice(
    state: dict[str, Any],
    recipient: str,
    content: str,
) -> None:
    """Queue a runner notice with its originating round for the agent's next turn."""
    agent_state(state, recipient)["inbox"].append(
        {
            "from": "runner",
            "to": recipient,
            # None leaves the [type=...] tag off the delivered notice.
            "message_type": (
                None if state["message_side_channel"] == "off" else "other"
            ),
            "content": content,
            "round": state["round"],
        }
    )


def pop_incoming_messages(state: dict[str, Any], actor: str) -> list[dict[str, Any]]:
    slot = agent_state(state, actor)
    messages = slot["inbox"]
    slot["inbox"] = []
    return messages


def _log_event(state: dict[str, Any], event: dict[str, Any]) -> None:
    event["event_id"] = len(state["events"])
    event["round"] = state["round"]
    event.setdefault("phase", state["phase"])
    state["events"].append(event)


def reset_message_delivery(state: dict[str, Any], actor: str) -> None:
    """Start a new delivery attempt for one agent."""
    agent_state(state, actor)["delivered"] = False
