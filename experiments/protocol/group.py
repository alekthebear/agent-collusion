"""Who takes part in an episode, who judges whom, and who talks to whom.

Every agent judges exactly one other agent (its reviewee) and is judged by exactly
one (its reviewer). In a pair those are the same agent; in a ring they differ, so no
agent judges the agent that judges it. Agents talk only along review links: each
link is one conversation between reviewer and reviewee.
"""

import argparse
from dataclasses import dataclass

from experiments.protocol.state import AGENT_IDS, AGENT_NAMES

GROUP_KINDS = ("pair", "ring")
DEFAULT_RING_SIZE = 3


@dataclass(frozen=True)
class Group:
    kind: str
    agent_ids: tuple[str, ...]
    # (reviewer, reviewee) links, in the order verdicts are collected.
    links: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        reviewers = sorted(reviewer for reviewer, _ in self.links)
        reviewees = sorted(reviewee for _, reviewee in self.links)
        if reviewers != sorted(self.agent_ids) or reviewees != sorted(self.agent_ids):
            raise ValueError(
                f"Every agent must judge exactly one agent and be judged by exactly "
                f"one: {self.links}"
            )
        if any(reviewer == reviewee for reviewer, reviewee in self.links):
            raise ValueError(f"An agent cannot judge itself: {self.links}")

    @property
    def is_pair(self) -> bool:
        return len(self.agent_ids) == 2

    def reviewee_of(self, agent_id: str) -> str:
        """The agent whose task this agent judges."""
        for reviewer, reviewee in self.links:
            if reviewer == agent_id:
                return reviewee
        raise ValueError(f"Unknown agent: {agent_id}")

    def reviewer_of(self, agent_id: str) -> str:
        """The agent that judges this agent's task."""
        for reviewer, reviewee in self.links:
            if reviewee == agent_id:
                return reviewer
        raise ValueError(f"Unknown agent: {agent_id}")

    def partners_of(self, agent_id: str) -> tuple[str, ...]:
        """The agents this agent talks with, in conversation order."""
        return tuple(
            second if first == agent_id else first
            for first, second in self.conversations()
            if agent_id in (first, second)
        )

    def conversations(self) -> tuple[tuple[str, str], ...]:
        """Each conversation as (first speaker, second speaker), in round order.

        A pair has one conversation, opened by the first agent. In a larger group each
        link is a conversation, opened by the agent being judged.
        """
        if self.is_pair:
            return ((self.agent_ids[0], self.agent_ids[1]),)
        return tuple((reviewee, reviewer) for reviewer, reviewee in self.links)

    def turns(self) -> tuple[tuple[str, str], ...]:
        """One round's turns as (sender, recipient), each conversation in turn."""
        return tuple(
            turn
            for first, second in self.conversations()
            for turn in ((first, second), (second, first))
        )

    def describe(self) -> dict[str, object]:
        """The group as the run record stores it."""
        return {
            "kind": self.kind,
            "agents": list(self.agent_ids),
            "links": [{"reviewer": r, "reviewee": e} for r, e in self.links],
        }


PAIR = Group(
    kind="pair",
    agent_ids=AGENT_IDS,
    links=((AGENT_IDS[0], AGENT_IDS[1]), (AGENT_IDS[1], AGENT_IDS[0])),
)


def ring_group(size: int = DEFAULT_RING_SIZE) -> Group:
    """Agents in name order, each judging the next and judged by the previous."""
    if not 3 <= size <= len(AGENT_NAMES):
        raise ValueError(f"A ring needs 3 to {len(AGENT_NAMES)} agents, got {size}")
    agent_ids = AGENT_NAMES[:size]
    return Group(
        kind="ring",
        agent_ids=agent_ids,
        links=tuple(
            (agent_ids[index], agent_ids[(index + 1) % size]) for index in range(size)
        ),
    )


def add_group_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("group")
    group.add_argument(
        "--group",
        choices=GROUP_KINDS,
        default="pair",
        help=(
            "pair: two agents judge each other (the paper's setting). ring: each "
            "agent judges the next, so no agent judges the agent that judges it."
        ),
    )
    group.add_argument(
        "--group-size",
        type=int,
        default=None,
        help=f"Ring size, 3 to {len(AGENT_NAMES)}. Default {DEFAULT_RING_SIZE}.",
    )


def group_from_args(args: argparse.Namespace) -> Group:
    kind = getattr(args, "group", "pair")
    size = getattr(args, "group_size", None)
    if kind == "pair":
        if size not in (None, 2):
            raise ValueError("--group pair always has 2 agents; drop --group-size")
        return PAIR
    if kind == "ring":
        return ring_group(DEFAULT_RING_SIZE if size is None else size)
    raise ValueError(f"Unknown group: {kind}")
