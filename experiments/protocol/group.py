"""Who takes part in an episode, who judges whom, and who talks to whom.

Every agent judges exactly one other agent (its reviewee) and is judged by exactly
one (its reviewer). In a pair those are the same agent; in a ring they differ, so no
agent judges the agent that judges it. With the ``links`` channel, agents talk only
along review links: each link is one conversation between reviewer and reviewee.
With the ``group`` channel, every agent posts to one chat that all of them see.
"""

import argparse
from dataclasses import dataclass

from experiments.protocol.state import AGENT_IDS, AGENT_NAMES

GROUP_KINDS = ("pair", "ring")
DEFAULT_RING_SIZE = 3
CHANNELS = ("links", "group")
# The recipient of a group-chat turn: every other agent.
GROUP_CHAT = "group"


@dataclass(frozen=True)
class Group:
    kind: str
    agent_ids: tuple[str, ...]
    # (reviewer, reviewee) links, in the order verdicts are collected.
    links: tuple[tuple[str, str], ...]
    channel: str = "links"

    def __post_init__(self) -> None:
        if self.channel not in CHANNELS:
            raise ValueError(f"Unknown channel: {self.channel}")
        if self.channel == "group" and len(self.agent_ids) == 2:
            raise ValueError("A pair already shares one conversation; use links")
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

    @property
    def is_group_chat(self) -> bool:
        return self.channel == "group"

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
        if self.is_group_chat:
            return tuple(a for a in self.agent_ids if a != agent_id)
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
        """One round's turns as (sender, recipient), each conversation in turn.

        In a group chat each agent posts once per round, in agent order.
        """
        if self.is_group_chat:
            return tuple((agent_id, GROUP_CHAT) for agent_id in self.agent_ids)
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
            "channel": self.channel,
        }


PAIR = Group(
    kind="pair",
    agent_ids=AGENT_IDS,
    links=((AGENT_IDS[0], AGENT_IDS[1]), (AGENT_IDS[1], AGENT_IDS[0])),
)


def ring_group(size: int = DEFAULT_RING_SIZE, channel: str = "links") -> Group:
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
        channel=channel,
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
    group.add_argument(
        "--channel",
        choices=CHANNELS,
        default="links",
        help=(
            "links: private conversations along review links. group: one group "
            "chat that every agent sees. Not for pairs."
        ),
    )


def group_from_args(args: argparse.Namespace) -> Group:
    kind = getattr(args, "group", "pair")
    size = getattr(args, "group_size", None)
    channel = getattr(args, "channel", "links")
    if kind == "pair":
        if size not in (None, 2):
            raise ValueError("--group pair always has 2 agents; drop --group-size")
        if channel != "links":
            raise ValueError("A pair already shares one conversation; drop --channel")
        return PAIR
    if kind == "ring":
        return ring_group(DEFAULT_RING_SIZE if size is None else size, channel)
    raise ValueError(f"Unknown group: {kind}")
