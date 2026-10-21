"""Who takes part in an episode, who judges whom, and who talks to whom.

In a pair or a ring, every agent judges exactly one other agent (its reviewee) and
is judged by exactly one (its reviewer). In a pair those are the same agent; in a
ring they differ, so no agent judges the agent that judges it. In a complete group,
every agent judges every other, and a task is accepted only if all its reviewers
accept it. With the ``links`` channel, agents talk only along review links; with the
``group`` channel, every agent posts to one chat that all of them see.
"""

import argparse
from dataclasses import dataclass

from experiments.protocol.state import AGENT_IDS, AGENT_NAMES

GROUP_KINDS = ("pair", "ring", "complete")
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
        if len(set(self.links)) != len(self.links):
            raise ValueError(f"A link appears twice: {self.links}")
        if any(reviewer == reviewee for reviewer, reviewee in self.links):
            raise ValueError(f"An agent cannot judge itself: {self.links}")
        for agent_id in self.agent_ids:
            if not self.reviewees_of(agent_id) or not self.reviewers_of(agent_id):
                raise ValueError(
                    f"Every agent must judge and be judged: {agent_id} in {self.links}"
                )

    @property
    def is_pair(self) -> bool:
        return len(self.agent_ids) == 2

    @property
    def is_group_chat(self) -> bool:
        return self.channel == "group"

    @property
    def single_review(self) -> bool:
        """Whether every agent judges exactly one agent and is judged by exactly one."""
        return all(
            len(self.reviewees_of(a)) == 1 and len(self.reviewers_of(a)) == 1
            for a in self.agent_ids
        )

    def reviewees_of(self, agent_id: str) -> tuple[str, ...]:
        """The agents whose tasks this agent judges, in verdict order."""
        return tuple(e for r, e in self.links if r == agent_id)

    def reviewers_of(self, agent_id: str) -> tuple[str, ...]:
        """The agents that judge this agent's task, in verdict order."""
        return tuple(r for r, e in self.links if e == agent_id)

    def reviewee_of(self, agent_id: str) -> str:
        """The one agent whose task this agent judges, in a single-review group."""
        (reviewee,) = self.reviewees_of(agent_id) or (None,)
        if reviewee is None:
            raise ValueError(f"Unknown agent: {agent_id}")
        return reviewee

    def reviewer_of(self, agent_id: str) -> str:
        """The one agent that judges this agent's task, in a single-review group."""
        (reviewer,) = self.reviewers_of(agent_id) or (None,)
        if reviewer is None:
            raise ValueError(f"Unknown agent: {agent_id}")
        return reviewer

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

        In a ring each link is a conversation, opened by the agent being judged. In a
        pair or a complete group, each two agents share one conversation, opened by
        the one earlier in agent order.
        """
        if self.is_pair or not self.single_review:
            return tuple(
                (first, second)
                for index, first in enumerate(self.agent_ids)
                for second in self.agent_ids[index + 1 :]
                if (first, second) in self.links or (second, first) in self.links
            )
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


def complete_group(size: int = DEFAULT_RING_SIZE, channel: str = "links") -> Group:
    """Agents in name order, each judging every other."""
    if not 3 <= size <= len(AGENT_NAMES):
        raise ValueError(
            f"A complete group needs 3 to {len(AGENT_NAMES)} agents, got {size}"
        )
    agent_ids = AGENT_NAMES[:size]
    return Group(
        kind="complete",
        agent_ids=agent_ids,
        links=tuple((r, e) for r in agent_ids for e in agent_ids if r != e),
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
            "agent judges the next, so no agent judges the agent that judges it. "
            "complete: each agent judges every other; a task is accepted only if "
            "all its reviewers accept it."
        ),
    )
    group.add_argument(
        "--group-size",
        type=int,
        default=None,
        help=(
            f"Size of a ring or complete group, 3 to {len(AGENT_NAMES)}. "
            f"Default {DEFAULT_RING_SIZE}."
        ),
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
    if kind == "complete":
        return complete_group(DEFAULT_RING_SIZE if size is None else size, channel)
    raise ValueError(f"Unknown group: {kind}")
