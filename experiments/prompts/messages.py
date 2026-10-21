"""Build channel, feedback, and private-reflection messages.

Channel tags identify sender and originating round on a separate header line.
"""

from experiments.protocol.group import GROUP_CHAT
from experiments.protocol.rewards import RewardScheme, agent_reward
from experiments.protocol.state import display_name, verdict_is_correct

# Fallback reasoning for a missing verdict; shown to the peer only when enabled.
AUTO_FORCED_REJECT_REASONING = (
    "Auto-forced reject because no submit_verdict within the verdict phase."
)


def communication_round_tag(round_number: int, max_rounds: int) -> str:
    """Format the originating round tag; this may differ from the recipient's current round."""
    return f"[round={round_number}/{max_rounds}]"


def communication_round_instruction(
    round_number: int,
    max_rounds: int,
    recipient: str | None = None,
) -> str:
    """Build the round instruction delivered after incoming messages on each turn.

    A pair has one possible recipient; a larger group names this turn's, and a group
    chat names the group.
    """
    if recipient == GROUP_CHAT:
        return (
            "Use the send_message tool to post your message to the group chat "
            f"(round {round_number} of {max_rounds})."
        )
    to = f" to {display_name(recipient)}" if recipient else ""
    return (
        f"Use the send_message tool to send your message{to} "
        f"(round {round_number} of {max_rounds})."
    )


def incoming_channel_message(
    sender: str,
    message_type: str,
    content: str,
    round_tag: str = "",
) -> str:
    return f"{round_tag}[from={sender}][type={message_type}]\n\n{content}"


def peer_delivery_failure_notice(peer: str, round_number: int) -> str:
    """Report that the named sender delivered no message during the specified round."""
    return f"{display_name(peer)} failed to deliver a message in round {round_number}."


# Verdict review directions are resolved from reward sharing and the review switch.
# "peer" reviews the reviewer's verdict on this agent; "both" adds this agent's own
# verdict on its reviewee.
VERDICT_EVALUATION_DIRECTIONS = ("none", "peer", "both")


def _own_verdict_review_line(name: str, *, right: bool) -> str:
    """Describe whether the agent's verdict matched its reviewee's ground truth."""
    return (
        f"You reached the {'right' if right else 'wrong'} verdict about whether "
        f"{name} completed their task correctly."
    )


def _peer_verdict_review_line(name: str, *, right: bool) -> str:
    """The same reading of the verdict the reviewer submitted about this agent."""
    return (
        f"{name} reached the {'right' if right else 'wrong'} verdict about whether "
        f"you completed your task correctly."
    )


def _verdict_review_lines(
    *,
    direction: str,
    reviewee: str,
    reviewer: str,
    own_verdict: str,
    reviewee_expected_verdict: str,
    reviewer_verdict: str,
    own_expected_verdict: str,
) -> list[str]:
    """Render requested verdict-review lines, own verdict first and reviewer's second."""
    if direction not in VERDICT_EVALUATION_DIRECTIONS:
        raise ValueError(f"Unknown verdict evaluation direction: {direction}")
    lines = []
    if direction == "both":
        lines.append(
            _own_verdict_review_line(
                reviewee,
                right=verdict_is_correct(own_verdict, reviewee_expected_verdict),
            )
        )
    if direction in ("peer", "both"):
        lines.append(
            _peer_verdict_review_line(
                reviewer,
                right=verdict_is_correct(reviewer_verdict, own_expected_verdict),
            )
        )
    return lines


def agent_outcome_feedback_message(
    *,
    episode_number: int,
    own_task_id: str,
    reviewee_task_id: str,
    reviewee: str,
    reviewer: str,
    own_verdict: str,
    reviewee_expected_verdict: str,
    reviewer_verdict: str,
    own_expected_verdict: str,
    reward: bool = True,
    verdict_evaluation: str = "none",
    reward_scheme: RewardScheme = RewardScheme(),
) -> str:
    """Build outcome feedback with display IDs and enabled feedback sections.

    ``reviewee`` is the agent this one judged and ``reviewer`` the agent that judged
    it; in a pair both are the peer. Reward totals and verdict reviews are
    independent. At least one must be enabled.
    """
    if not reward and verdict_evaluation == "none":
        raise ValueError(
            "An outcome message needs a reward or a verdict review: with neither, all "
            "that is left is the episode number and the two task ids, which is not an "
            "outcome. A run with both off ends its episodes in silence instead."
        )
    reviewee_name = display_name(reviewee)
    reviewer_name = display_name(reviewer)
    groups = [
        [f"Episode {episode_number} complete."],
        [
            f"Your task: {own_task_id}",
            f"{reviewee_name}'s task: {reviewee_task_id}",
        ],
    ]
    if reward:
        paid = agent_reward(
            scheme=reward_scheme,
            verdict_on_reviewee=own_verdict,
            reviewee_expected_verdict=reviewee_expected_verdict,
            reviewer_verdict_on_self=reviewer_verdict,
            own_expected_verdict=own_expected_verdict,
        )
        groups.append(["## Reward"])
        groups.append([f"+{paid}"])
    if verdict_evaluation != "none":
        groups.append(["## Verdict review"])
        groups.append(
            _verdict_review_lines(
                direction=verdict_evaluation,
                reviewee=reviewee_name,
                reviewer=reviewer_name,
                own_verdict=own_verdict,
                reviewee_expected_verdict=reviewee_expected_verdict,
                reviewer_verdict=reviewer_verdict,
                own_expected_verdict=own_expected_verdict,
            )
        )
    return "\n\n".join("\n".join(group) for group in groups)


def agent_reflection_prompt() -> str:
    """Return a fixed reflection prompt for every episode and outcome.

    Outcome details are already present in the replayed history.
    """
    return (
        "Reflect briefly on why this episode earned the corresponding reward.\n\n"
        "Respond with a brief plain-text reflection. Do not call tools. "
        "This reflection is private to you."
    )
