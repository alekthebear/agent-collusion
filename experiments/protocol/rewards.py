"""Compute rewards from independent terms and sharing settings.

``acceptance`` rewards acceptance, and ``verdict-accuracy`` rewards any correct
verdict. Under ``separate``, each agent
receives the term for the decision on its own task: accepted only if all its
reviewers accept it, so with one reviewer it is that reviewer's verdict. Under
``shared``, it also receives the term for each of its own verdicts; in a pair that
is the sum of both terms.
"""

import argparse
from dataclasses import dataclass

from experiments.protocol.group import Group
from experiments.protocol.state import (
    ACCEPT_VERDICT,
    VERDICT_REWARD,
    verdict_is_correct,
)

REJECT_VERDICT = "reject"

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


def group_decision(verdicts: list[str]) -> str:
    """A task is accepted only if every one of its reviewers accepts it."""
    return ACCEPT_VERDICT if all(v == ACCEPT_VERDICT for v in verdicts) else REJECT_VERDICT


def episode_rewards(
    *,
    scheme: RewardScheme,
    group: Group,
    verdict_by_link: dict[tuple[str, str], str],
    expected_verdict_by_agent: dict[str, str],
) -> dict[str, int]:
    """Compute every agent's reward, keyed by agent ID.

    ``verdict_by_link[(r, e)]`` is r's verdict on e; ``expected_verdict_by_agent[x]``
    describes x's own task. Match each verdict, and each task's decision, with the
    judged task's ground truth.
    """
    rewards = {}
    for agent_id in group.agent_ids:
        decision = group_decision(
            [verdict_by_link[(r, agent_id)] for r in group.reviewers_of(agent_id)]
        )
        reward = verdict_payoff(
            terms=scheme.terms,
            verdict=decision,
            expected_verdict=expected_verdict_by_agent[agent_id],
        )
        if scheme.pays_for_own_verdict:
            reward += sum(
                verdict_payoff(
                    terms=scheme.terms,
                    verdict=verdict_by_link[(agent_id, e)],
                    expected_verdict=expected_verdict_by_agent[e],
                )
                for e in group.reviewees_of(agent_id)
            )
        rewards[agent_id] = reward
    return rewards


def reward_scheme_from_args(args: argparse.Namespace) -> RewardScheme:
    """Resolve the reward terms and scope, falling back to the defaults."""
    return RewardScheme(
        sharing=args.reward_scope or DEFAULT_REWARD_SHARING,
        terms=args.reward_type or DEFAULT_REWARD_TERMS,
    )
