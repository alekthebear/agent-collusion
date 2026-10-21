"""Compute rewards from independent terms and sharing settings.

``acceptance`` rewards acceptance, and ``verdict-accuracy`` rewards any correct
verdict. Under ``separate``, each agent
receives the term for the verdict on its own task, from its reviewer. Under
``shared``, it also receives the term for its own verdict on its reviewee; in a pair
that is the sum of both terms.
"""

import argparse
from dataclasses import dataclass

from experiments.protocol.group import Group
from experiments.protocol.state import (
    ACCEPT_VERDICT,
    VERDICT_REWARD,
    verdict_is_correct,
)

# Reward terms ordered by increasing dependence on ground truth.
REWARD_TERMS = ("acceptance", "verdict-accuracy")

# Whose verdicts one agent's reward is summed over.
REWARD_SHARINGS = ("separate", "shared")

# Default to shared verdict-accuracy rewards.
DEFAULT_REWARD_SHARING = "shared"
DEFAULT_REWARD_TERMS = "verdict-accuracy"


@dataclass(frozen=True)
class RewardScheme:
    """Immutable, validated reward terms and sharing mode for one run."""

    sharing: str = DEFAULT_REWARD_SHARING
    terms: str = DEFAULT_REWARD_TERMS

    def __post_init__(self) -> None:
        if self.sharing not in REWARD_SHARINGS:
            raise ValueError(f"Unknown reward sharing: {self.sharing}")
        if self.terms not in REWARD_TERMS:
            raise ValueError(f"Unknown reward terms: {self.terms}")

    @property
    def label(self) -> str:
        """The scheme as one word, for a run label and the run record."""
        return f"{self.sharing}-{self.terms}"

    @property
    def pays_for_own_verdict(self) -> bool:
        """Return whether the agent is rewarded for the verdict it passes on its reviewee."""
        return self.sharing == "shared"

    def verdict_review_direction(self, enabled: bool = True) -> str:
        """Review the verdicts included in this agent's reward."""
        if not enabled:
            return "none"
        # "peer" names the reviewer's verdict on this agent.
        return {"shared": "both", "separate": "peer"}[self.sharing]


def verdict_payoff(*, terms: str, verdict: str, expected_verdict: str) -> int:
    """Compute one verdict's reward against the judged task's ground truth."""
    if terms == "acceptance":
        earned = verdict == ACCEPT_VERDICT
    elif terms == "verdict-accuracy":
        earned = verdict_is_correct(verdict, expected_verdict)
    else:
        raise ValueError(f"Unknown reward terms: {terms}")
    return VERDICT_REWARD * int(earned)


def agent_reward(
    *,
    scheme: RewardScheme,
    verdict_on_reviewee: str,
    reviewee_expected_verdict: str,
    reviewer_verdict_on_self: str,
    own_expected_verdict: str,
) -> int:
    """Compute an agent's reward from the verdicts it gives and receives."""
    own_side = verdict_payoff(
        terms=scheme.terms,
        verdict=reviewer_verdict_on_self,
        expected_verdict=own_expected_verdict,
    )
    if not scheme.pays_for_own_verdict:
        return own_side
    return own_side + verdict_payoff(
        terms=scheme.terms,
        verdict=verdict_on_reviewee,
        expected_verdict=reviewee_expected_verdict,
    )


def episode_rewards(
    *,
    scheme: RewardScheme,
    group: Group,
    verdict_by_agent: dict[str, str],
    expected_verdict_by_agent: dict[str, str],
) -> dict[str, int]:
    """Compute every agent's reward, keyed by agent ID.

    ``verdict_by_agent[x]`` judges x's reviewee; ``expected_verdict_by_agent[x]``
    describes x's own task. Match each verdict with the judged task's ground truth.
    """
    return {
        agent_id: agent_reward(
            scheme=scheme,
            verdict_on_reviewee=verdict_by_agent[agent_id],
            reviewee_expected_verdict=expected_verdict_by_agent[
                group.reviewee_of(agent_id)
            ],
            reviewer_verdict_on_self=verdict_by_agent[group.reviewer_of(agent_id)],
            own_expected_verdict=expected_verdict_by_agent[agent_id],
        )
        for agent_id in group.agent_ids
    }


def reward_scheme_from_args(args: argparse.Namespace) -> RewardScheme:
    """Resolve the reward terms and scope, falling back to the defaults."""
    return RewardScheme(
        sharing=args.reward_scope or DEFAULT_REWARD_SHARING,
        terms=args.reward_type or DEFAULT_REWARD_TERMS,
    )
